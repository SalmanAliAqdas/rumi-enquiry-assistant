"""Short database claims surround a bounded model request; no transaction spans it."""

import asyncio
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import or_, update
from sqlmodel import Session, select

from app.models import Enquiry, ProcessingAttempt, Workflow, utcnow
from app.services import ProcessingFailure
from app.shared_limits import run_processor

ERRORS = {
    "shared_limit": "Shared Gemini daily or total budget reached. Review manually; no fallback.",
    "shared_busy": "Another Gemini request is active. Retry manually later.",
    "shared_unavailable": "Shared usage guard unavailable. No model request was authorized.",
    "local_limit": (
        "Local processing limit reached (6 starts per minute). Wait at least a minute before "
        "retrying manually. The enquiry and saved draft are preserved."
    ),
    "local_busy": (
        "Two Gemini attempts are already active in this process. "
        "Wait for one to finish, then retry."
    ),
    "missing_key": "Set the server-side GEMINI_API_KEY and restart the app, then retry.",
    "configuration": (
        "Check processor mode, model, timeout (1–60s), and token limit (256–2000); "
        "restart and retry."
    ),
    "faq_configuration": (
        "Create or repair the private FAQ JSON file, then retry. "
        "Entries must have unique IDs and explicit approval flags."
    ),
    "authentication": "Check the server-side key and its project permissions; restart and retry.",
    "model_unavailable": (
        "Check that the configured model is available to the project. No fallback was attempted."
    ),
    "quota": (
        "Free quota or rate limit reached. Check AI Studio and wait before a manual retry; "
        "no billing change was made."
    ),
    "timeout": (
        "Processing timed out. The enquiry is saved; retry manually when the provider is available."
    ),
    "provider": "The provider could not complete the request. The enquiry is saved; retry later.",
    "blocked": (
        "The provider blocked or did not finish the response. Review the original enquiry manually."
    ),
    "empty_response": "The provider returned no usable text. Review manually or retry later.",
    "output_limit": (
        "The provider reached the output limit. Review the configured token budget before retrying."
    ),
    "invalid_output": (
        "The generated result failed validation. Review manually or retry; no result was applied."
    ),
    "invalid_sources": "The response cited unknown or unapproved FAQ IDs. No result was applied.",
    "interrupted": "Processing was interrupted. The enquiry is saved; retry manually.",
}


async def process_enquiry(app, enquiry_id: int, *, initial: bool = False) -> bool:
    now = utcnow()
    token = uuid4().hex
    # A crashed request's claim can be recovered after 90 seconds. Normal calls
    # are bounded to at most 60 seconds, and late results cannot win a newer claim.
    with Session(app.state.engine) as db:
        eligible = or_(
            Enquiry.processing_status.in_(["Pending", "Failed"]),
            (Enquiry.processing_status == "Processing")
            & (Enquiry.processing_started_at < now - timedelta(seconds=90)),
        )
        claim = db.exec(
            update(Enquiry)
            .where(Enquiry.id == enquiry_id, eligible)
            .values(
                processing_status="Processing",
                processing_token=token,
                processing_started_at=now,
                processing_mode=app.state.processing_mode,
                processing_error_code=None,
                processing_error=None,
            )
        )
        if claim.rowcount != 1:
            db.rollback()
            return False
        row = db.get(Enquiry, enquiry_id)
        message = row.message
        # Mark an older crashed attempt as interrupted without deleting history.
        db.exec(
            update(ProcessingAttempt)
            .where(
                ProcessingAttempt.enquiry_id == enquiry_id, ProcessingAttempt.status == "Processing"
            )
            .values(status="Failed", error_code="interrupted", finished_at=now)
        )
        db.add(
            ProcessingAttempt(
                id=token,
                enquiry_id=enquiry_id,
                mode=app.state.processing_mode,
                model=app.state.processing_model,
            )
        )
        db.commit()
    code = None
    result = None
    sources = []
    cancelled = False
    try:
        result = await run_processor(app, message)
        sources = result._faq_sources
    except TimeoutError:
        code = "timeout"
    except ProcessingFailure as exc:
        code = exc.code if exc.code in ERRORS else "provider"
    except asyncio.CancelledError:
        code, cancelled = "interrupted", True
    except Exception:
        # Never persist/log raw exceptions, provider payloads, keys, or customer data.
        code = "provider"
    with Session(app.state.engine) as db:
        finish = db.exec(
            update(Enquiry)
            .where(
                Enquiry.id == enquiry_id,
                Enquiry.processing_token == token,
            )
            .values(processing_token=None, updated_at=utcnow())
        )
        if finish.rowcount != 1:
            db.rollback()
            return False
        row = db.get(Enquiry, enquiry_id)
        attempt = db.get(ProcessingAttempt, token)
        attempt.finished_at = row.updated_at
        if code:
            row.processing_status = attempt.status = "Failed"
            row.processing_error_code = attempt.error_code = code
            row.processing_error = ERRORS[code]
        else:
            row.processing_status = attempt.status = "Completed"
            candidate = {"id": token, **result.model_dump(mode="json"), "faq_sources": sources}
            attempt.result = candidate
            # Only a pristine first submission may populate its initial draft.
            # All retries and concurrent human edits receive a separate candidate.
            if initial and row.draft_revision == 0 and row.workflow_status == Workflow.NEW:
                apply_fields(row, candidate)
            else:
                row.candidate = candidate
        db.add(row)
        db.add(attempt)
        db.commit()
    if cancelled:
        raise asyncio.CancelledError
    return True


def apply_fields(row: Enquiry, candidate: dict):
    for name in (
        "category",
        "summary",
        "reply_draft",
        "clarification_questions",
        "needs_clarification",
        "review_reason",
        "faq_sources",
    ):
        setattr(row, name, candidate[name])
    row.candidate = None


def attempts_for(db: Session, enquiry_id: int):
    return db.exec(
        select(ProcessingAttempt)
        .where(ProcessingAttempt.enquiry_id == enquiry_id)
        .order_by(ProcessingAttempt.started_at.desc())
    ).all()
