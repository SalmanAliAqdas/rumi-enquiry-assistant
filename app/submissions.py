"""Shared idempotent, save-first storage for public and private submissions."""

from typing import NamedTuple
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import Enquiry
from app.schemas import Submission


class SavedSubmission(NamedTuple):
    id: int
    reference: str
    created: bool


def existing_submission(db: Session, data: Submission) -> SavedSubmission | None:
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
    saved = SavedSubmission(existing.id, existing.reference, False)
    db.rollback()  # End the authentication/read transaction before returning.
    return saved


def save_submission(
    db: Session, data: Submission, mode: str, *, fictional_test: bool = False
) -> SavedSubmission:
    if saved := existing_submission(db, data):
        return saved
    fields = {"reference": f"REA-TEST-{uuid4().hex.upper()}"} if fictional_test else {}
    enquiry = Enquiry(
        submission_key=str(data.submission_key),
        name=data.name,
        email=str(data.email),
        message=data.message,
        processing_mode=mode,
        **fields,
    )
    db.add(enquiry)
    try:
        db.flush()
        saved = SavedSubmission(enquiry.id, enquiry.reference, True)
        db.commit()
    except IntegrityError:
        # A concurrent retry must return the existing record, not process it twice.
        db.rollback()
        if saved := existing_submission(db, data):
            return saved
        raise
    return saved
