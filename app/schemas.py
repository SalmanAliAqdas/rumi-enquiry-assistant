from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer

from app.models import Category, Workflow


class Submission(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=254)
    message: str = Field(min_length=20, max_length=3000)
    submission_key: UUID


class Receipt(BaseModel):
    reference: str
    message: str = "Enquiry received. Keep this reference for your records."


class DraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply_draft: str = Field(min_length=1, max_length=6000)
    workflow_status: Workflow


class EnquiryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reference: str
    name: str
    email: str
    message: str
    category: Category
    summary: str
    reply_draft: str
    processing_mode: str
    processing_status: str
    workflow_status: Workflow
    created_at: datetime
    updated_at: datetime
    clarification_questions: list[str]
    faq_sources: list[dict]
    needs_clarification: bool
    review_reason: str | None
    processing_error_code: str | None
    processing_error: str | None
    candidate: dict | None
    draft_revision: int

    @field_serializer("created_at", "updated_at")
    def serialize_utc(self, value: datetime) -> str:
        # SQLite stores naive datetimes; all writes in this app are UTC.
        return value.replace(tzinfo=UTC).isoformat()


class EnquiryPage(BaseModel):
    items: list[EnquiryRead]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]


class ApplyCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str = Field(min_length=32, max_length=32)
    draft_revision: int = Field(ge=0)
