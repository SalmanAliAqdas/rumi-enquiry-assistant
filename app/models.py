from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class Category(StrEnum):
    WEBSITE = "Website"
    MOBILE = "Mobile application"
    AUTOMATION = "Automation"
    OTHER = "Other / needs clarification"


class Workflow(StrEnum):
    NEW = "New"
    REVIEWED = "Reviewed"
    CLOSED = "Closed"


class Enquiry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    reference: str = Field(default_factory=lambda: f"REA-{uuid4().hex.upper()}", unique=True)
    submission_key: str = Field(unique=True, index=True)
    name: str
    email: str
    message: str
    category: Category = Category.OTHER
    summary: str = ""
    reply_draft: str = ""
    processing_mode: str = "demo"
    processing_status: str = "Pending"
    workflow_status: Workflow = Workflow.NEW
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    clarification_questions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    faq_sources: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    needs_clarification: bool = False
    review_reason: str | None = None
    processing_error_code: str | None = None
    processing_error: str | None = None
    processing_started_at: datetime | None = None
    processing_token: str | None = None
    candidate: dict | None = Field(default=None, sa_column=Column(JSON))
    draft_revision: int = 0


class ProcessingAttempt(SQLModel, table=True):
    id: str = Field(primary_key=True)
    enquiry_id: int = Field(foreign_key="enquiry.id", index=True)
    mode: str
    model: str | None = None
    status: str = "Processing"
    error_code: str | None = None
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    result: dict | None = Field(default=None, sa_column=Column(JSON))


class Admin(SQLModel, table=True):
    # A fixed primary key enforces a single administrator.
    id: int = Field(default=1, primary_key=True)
    username: str = Field(unique=True)
    password_hash: str


class WebSession(SQLModel, table=True):
    token_hash: str = Field(primary_key=True)
    csrf_token: str
    admin_id: int | None = Field(default=None, foreign_key="admin.id")
    expires_at: datetime
