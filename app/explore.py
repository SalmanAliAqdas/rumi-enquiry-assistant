"""Public fictional workflow, with no private inbox queries or record lookup route."""

import asyncio
import json
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from sqlmodel import Session

from app.auth import COOKIE, csrf_protect, hash_token, issue_session
from app.db import get_db
from app.models import DemoRun, WebSession, utcnow
from app.processing import ERRORS
from app.services import DemoProcessor, ProcessingFailure
from app.shared_limits import run_processor

router = APIRouter(include_in_schema=False)
SAMPLES = json.loads((Path(__file__).parent / "demo_data" / "samples.json").read_text("utf-8"))


def sample_for(sample_id):
    for sample in SAMPLES:
        if sample["id"] == sample_id:
            return sample
    raise HTTPException(404, "Fictional sample not found.")


def render(request, *, session=None, sample=None, result=None, kind=None, error=None, headers=None):
    return request.app.state.templates.TemplateResponse(
        request,
        "explore.html",
        {
            "samples": SAMPLES,
            "sample": sample,
            "result": result,
            "kind": kind,
            "error": error,
            "csrf_token": session.csrf_token if session else "",
            "live_enabled": request.app.state.settings.public_demo_live,
        },
        headers=headers,
    )


@router.get("/explore")
def explore(request: Request, db: Session = Depends(get_db)):
    # Anonymous cookie exists solely for CSRF, never grants inbox access.
    from datetime import UTC

    token = request.cookies.get(COOKIE)
    session = db.get(WebSession, hash_token(token)) if token else None
    if session and session.expires_at.replace(tzinfo=UTC) > utcnow():
        return render(request, session=session)
    response = Response()
    session = issue_session(request, response, db)
    return render(request, session=session, headers={"set-cookie": response.headers["set-cookie"]})


@router.post("/explore/simulate", dependencies=[Depends(csrf_protect)])
async def simulate(request: Request, sample_id: Annotated[str, Form(max_length=40)]):
    sample = sample_for(sample_id)
    result = await DemoProcessor().process(sample["message"])
    # Deterministic output is not a saved record or a model result.
    return render(request, sample=sample, result=result.model_dump(mode="json"), kind="Simulated")


@router.post("/explore/live", dependencies=[Depends(csrf_protect)])
async def live(request: Request, sample_id: Annotated[str, Form(max_length=40)]):
    if not request.app.state.settings.public_demo_live:
        raise HTTPException(403, "Live generation is disabled.")
    sample = sample_for(sample_id)
    run_id = uuid4().hex
    # Persist fixed fictional input before processing; no transaction spans a model call.
    with Session(request.app.state.engine) as db:
        db.add(DemoRun(id=run_id, sample_id=sample["id"], kind="Live-generated"))
        db.commit()
    error = None
    result = None
    cancelled = False
    try:
        result = (await run_processor(request.app, sample["message"])).model_dump(mode="json")
    except ProcessingFailure as exc:
        error = exc.code if exc.code in ERRORS else "provider"
    except TimeoutError:
        error = "timeout"
    except asyncio.CancelledError:
        error, cancelled = "interrupted", True
    except Exception:
        error = "provider"
    with Session(request.app.state.engine) as db:
        row = db.get(DemoRun, run_id)
        row.status = "Failed" if error else "Completed"
        row.result, row.error_code = result, error
        db.add(row)
        db.commit()
    if cancelled:
        raise asyncio.CancelledError
    return render(
        request,
        sample=sample,
        result=result,
        kind="Live-generated (saved fictional run)",
        error=ERRORS.get(error),
    )
