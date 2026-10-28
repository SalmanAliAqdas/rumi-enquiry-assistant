from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from starlette.exceptions import HTTPException
from starlette.responses import RedirectResponse

from app.db import get_db
from app.models import Enquiry
from app.processing import process_enquiry
from app.schemas import Receipt, Submission

router = APIRouter()


@router.get("/", include_in_schema=False)
def enquiry_form(request: Request):
    if request.app.state.settings.portfolio_mode:
        return RedirectResponse("/explore", status_code=303)
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
async def submit(data: Submission, request: Request, db: Session = Depends(get_db)):
    if request.app.state.settings.portfolio_mode:
        raise HTTPException(403, "Portfolio accepts only the fictional Explore Demo samples.")
    if receipt := existing_receipt(db, data):
        return receipt
    enquiry = Enquiry(
        submission_key=str(data.submission_key),
        name=data.name,
        email=str(data.email),
        message=data.message,
        processing_mode=request.app.state.processing_mode,
    )
    db.add(enquiry)
    try:
        db.flush()
        enquiry_id, reference = enquiry.id, enquiry.reference
        db.commit()
    except IntegrityError:
        # Concurrent retries of the same submission must create just one record.
        db.rollback()
        if receipt := existing_receipt(db, data):
            return receipt
        raise
    await process_enquiry(request.app, enquiry_id, initial=True)
    return Receipt(reference=reference)
