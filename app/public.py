from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from starlette.exceptions import HTTPException

from app.db import get_db
from app.models import Enquiry
from app.schemas import Receipt, Submission

router = APIRouter()


@router.get("/", include_in_schema=False)
def enquiry_form(request: Request):
    return request.app.state.templates.TemplateResponse(request, "form.html")


def existing_receipt(db: Session, data: Submission) -> Receipt | None:
    existing = db.exec(
        select(Enquiry).where(Enquiry.submission_key == str(data.submission_key))
    ).first()
    if existing is None:
        return None
    if (existing.name, existing.email, existing.message) != (
        data.name,
        str(data.email),
        data.message,
    ):
        raise HTTPException(
            409, "This submission token was already used. Reload for a new enquiry."
        )
    return Receipt(reference=existing.reference)


@router.post("/api/enquiries", response_model=Receipt, status_code=201, tags=["Public"])
def submit(data: Submission, request: Request, db: Session = Depends(get_db)):
    if receipt := existing_receipt(db, data):
        return receipt
    result = request.app.state.processor.process(data.message)
    enquiry = Enquiry(
        submission_key=str(data.submission_key),
        name=data.name,
        email=str(data.email),
        message=data.message,
        category=result.category,
        summary=result.summary,
        reply_draft=result.reply_draft,
    )
    db.add(enquiry)
    try:
        db.commit()
    except IntegrityError:
        # Concurrent retries of the same submission must create just one record.
        db.rollback()
        if receipt := existing_receipt(db, data):
            return receipt
        raise
    db.refresh(enquiry)
    return Receipt(reference=enquiry.reference)
