from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BeforeValidator
from sqlalchemy import func, or_
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
from app.schemas import DraftUpdate, EnquiryPage, EnquiryRead

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
        page: int = Query(default=1, ge=1),
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
    admin = verify_login(db, username, password)
    if not admin:
        return request.app.state.templates.TemplateResponse(
            request,
            "login.html",
            {"csrf_token": session.csrf_token, "error": "Username or password is incorrect."},
            status_code=401,
        )
    response = RedirectResponse("/admin", status_code=303)
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
            "filters": filters,
            "categories": list(Category),
            "statuses": list(Workflow),
            "previous_url": request.url.include_query_params(page=filters.page - 1),
            "next_url": request.url.include_query_params(page=filters.page + 1),
        },
    )


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
            "statuses": list(Workflow),
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
    enquiry = get_enquiry(enquiry_id, db)
    enquiry.reply_draft = data.reply_draft
    enquiry.workflow_status = data.workflow_status
    enquiry.updated_at = utcnow()
    db.add(enquiry)
    db.commit()
    db.refresh(enquiry)
    return enquiry
