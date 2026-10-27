from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

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
    category: Category
    summary: str
    reply_draft: str
    processing_mode: str = "demo"
    processing_status: str = "Completed"
    workflow_status: Workflow = Workflow.NEW
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


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
