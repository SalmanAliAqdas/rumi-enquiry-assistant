from fastapi import APIRouter, Depends, Request
from sqlmodel import Session
from starlette.exceptions import HTTPException
from starlette.responses import RedirectResponse

from app.db import get_db
from app.processing import process_enquiry
from app.schemas import Receipt, Submission
from app.submissions import save_submission

router = APIRouter()


@router.get("/", include_in_schema=False)
def enquiry_form(request: Request):
    if request.app.state.settings.portfolio_mode:
        return RedirectResponse("/explore", status_code=303)
    return request.app.state.templates.TemplateResponse(request, "form.html")


@router.post("/api/enquiries", response_model=Receipt, status_code=201, tags=["Public"])
async def submit(data: Submission, request: Request, db: Session = Depends(get_db)):
    if request.app.state.settings.portfolio_mode:
        raise HTTPException(403, "Portfolio accepts only the fictional Explore Demo samples.")
    saved = save_submission(db, data, request.app.state.processing_mode)
    if saved.created:
        await process_enquiry(request.app, saved.id, initial=True)
    return Receipt(reference=saved.reference)
