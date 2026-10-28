from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BeforeValidator
from sqlalchemy import func, or_, update
from sqlmodel import Session, select

from app.auth import (
    COOKIE,
    csrf_protect,
    current_session,
    issue_session,
    require_admin,
    verify_login,
)
from app.db import get_db
from app.models import Category, Enquiry, WebSession, Workflow, utcnow
from app.processing import attempts_for, process_enquiry
from app.review import configuration_status, next_action
from app.schemas import (
    ApplyCandidate,
    ConfigurationStatus,
    DraftUpdate,
    EnquiryPage,
    EnquiryRead,
    Submission,
)
from app.submissions import save_submission

router = APIRouter()
private_api = APIRouter(
    prefix="/api/admin", dependencies=[Depends(require_admin)], tags=["Private"]
)


class Filters:
    def __init__(
        self,
        q: str = Query(default="", max_length=100),
        category: Annotated[Category | None, BeforeValidator(lambda v: v or None)] = None,
        status: Annotated[Workflow | None, BeforeValidator(lambda v: v or None)] = None,
        page: int = Query(default=1, ge=1, le=1_000_000),
        page_size: int = Query(default=10, ge=1, le=50),
    ):
        self.q = q.strip()
        self.category = category
        self.status = status
        self.page = page
        self.page_size = page_size


def find_enquiries(db: Session, filters: Filters) -> EnquiryPage:
    query = select(Enquiry)
    if filters.q:
        query = query.where(
            or_(
                Enquiry.name.contains(filters.q, autoescape=True),
                Enquiry.email.contains(filters.q, autoescape=True),
                Enquiry.message.contains(filters.q, autoescape=True),
                Enquiry.reference.contains(filters.q, autoescape=True),
            )
        )
    if filters.category:
        query = query.where(Enquiry.category == filters.category)
    if filters.status:
        query = query.where(Enquiry.workflow_status == filters.status)
    total = db.exec(select(func.count()).select_from(query.subquery())).one()
    rows = db.exec(
        query.order_by(Enquiry.created_at.desc(), Enquiry.id.desc())
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
    ).all()
    counts = {status.value: 0 for status in Workflow}
    for status, count in db.exec(
        select(Enquiry.workflow_status, func.count()).group_by(Enquiry.workflow_status)
    ).all():
        counts[status.value] = count
    return EnquiryPage(
        items=[EnquiryRead.model_validate(row) for row in rows],
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        counts=counts,
    )


def get_enquiry(enquiry_id: int, db: Session) -> Enquiry:
    enquiry = db.get(Enquiry, enquiry_id)
    if not enquiry:
        raise HTTPException(404, "Enquiry not found.")
    return enquiry


@router.get("/admin/login", include_in_schema=False)
def login_page(request: Request, db: Session = Depends(get_db)):
    response = Response()
    session = issue_session(request, response, db)
    return request.app.state.templates.TemplateResponse(
        request,
        "login.html",
        {"csrf_token": session.csrf_token, "error": None},
        headers={"set-cookie": response.headers["set-cookie"]},
    )


@router.post("/admin/login", dependencies=[Depends(csrf_protect)], include_in_schema=False)
def login(
    request: Request,
    username: Annotated[str, Form(min_length=1, max_length=100)],
    password: Annotated[str, Form(min_length=1, max_length=256)],
    session: WebSession = Depends(current_session),
    db: Session = Depends(get_db),
):
    limit_code, wait = request.app.state.login_budget.enter()
    if limit_code:
        return request.app.state.templates.TemplateResponse(
            request,
            "login.html",
            {
                "csrf_token": session.csrf_token,
                "error": f"Too many sign-in attempts. Wait {wait} seconds before trying again.",
            },
            status_code=429,
            headers={"Retry-After": str(wait)},
        )
    try:
        admin = verify_login(db, username, password)
    finally:
        request.app.state.login_budget.leave()
    if not admin:
        return request.app.state.templates.TemplateResponse(
            request,
            "login.html",
            {"csrf_token": session.csrf_token, "error": "Username or password is incorrect."},
            status_code=401,
        )
    response = RedirectResponse("/admin", status_code=303)
    request.app.state.login_budget.reset()
    issue_session(request, response, db, admin.id)
    return response


@router.post("/admin/logout", dependencies=[Depends(csrf_protect)], include_in_schema=False)
def logout(session: WebSession = Depends(require_admin), db: Session = Depends(get_db)):
    db.delete(session)
    db.commit()
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
    return response


@router.get("/admin", include_in_schema=False)
def dashboard(
    request: Request,
    session: WebSession = Depends(require_admin),
    db: Session = Depends(get_db),
    filters: Filters = Depends(),
):
    results = find_enquiries(db, filters)
    return request.app.state.templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "csrf_token": session.csrf_token,
            "results": results,
            "configuration": configuration_status(request.app),
            "next_action": next_action,
            "filters": filters,
            "categories": list(Category),
            "statuses": list(Workflow),
            "previous_url": request.url.include_query_params(page=filters.page - 1),
            "next_url": request.url.include_query_params(page=filters.page + 1),
        },
    )


@router.get("/admin/enquiries/new", include_in_schema=False)
def new_test_enquiry(request: Request, session: WebSession = Depends(require_admin)):
    return request.app.state.templates.TemplateResponse(
        request, "new_test_enquiry.html", {"csrf_token": session.csrf_token}
    )


@private_api.post(
    "/enquiries",
    response_model=EnquiryRead,
    status_code=201,
    dependencies=[Depends(csrf_protect)],
)
async def submit_test_enquiry(data: Submission, request: Request, db: Session = Depends(get_db)):
    saved = save_submission(db, data, request.app.state.processing_mode, fictional_test=True)
    if saved.created:
        await process_enquiry(request.app, saved.id, initial=True)
    return get_enquiry(saved.id, db)


@router.get("/admin/enquiries/{enquiry_id}", include_in_schema=False)
def details(
    enquiry_id: int,
    request: Request,
    session: WebSession = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return request.app.state.templates.TemplateResponse(
        request,
        "detail.html",
        {
            "csrf_token": session.csrf_token,
            "enquiry": get_enquiry(enquiry_id, db),
            "configuration": configuration_status(request.app),
            "next_action": next_action,
            "statuses": list(Workflow),
            "attempts": attempts_for(db, enquiry_id),
        },
    )


@private_api.get("/enquiries", response_model=EnquiryPage)
def list_api(db: Session = Depends(get_db), filters: Filters = Depends()):
    return find_enquiries(db, filters)


@private_api.get("/enquiries/{enquiry_id}", response_model=EnquiryRead)
def read_api(enquiry_id: int, db: Session = Depends(get_db)):
    return get_enquiry(enquiry_id, db)


@private_api.patch(
    "/enquiries/{enquiry_id}",
    response_model=EnquiryRead,
    dependencies=[Depends(csrf_protect)],
)
def edit_api(enquiry_id: int, data: DraftUpdate, db: Session = Depends(get_db)):
    if not data.reply_draft.strip():
        raise HTTPException(422, "Reply draft cannot be blank.")
    get_enquiry(enquiry_id, db)
    query = update(Enquiry).where(Enquiry.id == enquiry_id)
    if data.expected_revision is not None:
        query = query.where(Enquiry.draft_revision == data.expected_revision)
    result = db.exec(
        query.values(
            reply_draft=data.reply_draft,
            workflow_status=data.workflow_status,
            draft_revision=Enquiry.draft_revision + 1,
            updated_at=utcnow(),
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            409,
            "The saved draft changed in another view. Copy your edits before reloading "
            "and reviewing the latest draft.",
        )
    db.commit()
    return get_enquiry(enquiry_id, db)


@private_api.get("/status", response_model=ConfigurationStatus)
def private_status(request: Request):
    return configuration_status(request.app)


@private_api.post(
    "/enquiries/{enquiry_id}/retry",
    dependencies=[Depends(csrf_protect)],
    response_model=EnquiryRead,
)
async def retry_api(enquiry_id: int, request: Request, db: Session = Depends(get_db)):
    get_enquiry(enquiry_id, db)
    db.rollback()  # End the authentication/read transaction before awaiting the provider.
    if not await process_enquiry(request.app, enquiry_id):
        raise HTTPException(
            409, "Only failed, pending, or interrupted (over 90 seconds) enquiries can be retried."
        )
    return EnquiryRead.model_validate(get_enquiry(enquiry_id, db))


@private_api.post(
    "/enquiries/{enquiry_id}/apply-candidate",
    dependencies=[Depends(csrf_protect)],
    response_model=EnquiryRead,
)
def apply_candidate(enquiry_id: int, data: ApplyCandidate, db: Session = Depends(get_db)):
    row = get_enquiry(enquiry_id, db)
    if not row.candidate or row.candidate["id"] != data.candidate_id:
        raise HTTPException(
            409, "Candidate changed or was already applied. Reload and review again."
        )
    candidate = row.candidate
    values = {
        name: candidate[name]
        for name in (
            "category",
            "summary",
            "reply_draft",
            "clarification_questions",
            "needs_clarification",
            "review_reason",
            "faq_sources",
        )
    }
    result = db.exec(
        update(Enquiry)
        .where(
            Enquiry.id == enquiry_id,
            Enquiry.draft_revision == data.draft_revision,
            Enquiry.candidate["id"].as_string() == data.candidate_id,
            Enquiry.processing_status != "Processing",
        )
        .values(
            **values, candidate=None, draft_revision=Enquiry.draft_revision + 1, updated_at=utcnow()
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            409, "The draft changed. Reload and review before applying this candidate."
        )
    db.commit()
    return get_enquiry(enquiry_id, db)
