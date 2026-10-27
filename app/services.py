"""Replaceable processors and a shared, bounded result schema."""

import re
from typing import Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    StrictBool,
    field_validator,
    model_validator,
)

from app.models import Category

DEMO_LABEL = "Demo processing — no AI model connected."


class ProcessingResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    category: Category
    summary: str = Field(min_length=1, max_length=500)
    reply_draft: str = Field(min_length=1, max_length=4000)
    clarification_questions: list[str] = Field(max_length=3)
    faq_ids: list[str] = Field(max_length=10)
    needs_clarification: StrictBool
    review_reason: str | None = Field(max_length=500)
    _faq_sources: list[dict] = PrivateAttr(default_factory=list)

    @field_validator("clarification_questions", "faq_ids")
    @classmethod
    def bound_items(cls, items: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 250 for item in items):
            raise ValueError("Items must contain 1–250 characters")
        if len(set(items)) != len(items):
            raise ValueError("Items must be unique")
        return items

    @model_validator(mode="after")
    def explain_review(self):
        if self.needs_clarification and not self.review_reason:
            raise ValueError("Clarification requires a review reason")
        return self


class ProcessingFailure(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class Processor(Protocol):
    async def process(self, message: str) -> ProcessingResult: ...


class DemoProcessor:
    keywords = {
        Category.WEBSITE: {"website", "websites", "web", "landing"},
        Category.MOBILE: {"mobile", "android", "ios", "iphone"},
        Category.AUTOMATION: {"automation", "automate", "workflow", "workflows"},
    }

    async def process(self, message: str) -> ProcessingResult:
        words = set(re.findall(r"\b\w+\b", message.lower()))
        matches = [category for category, keywords in self.keywords.items() if words & keywords]
        category = matches[0] if len(matches) == 1 else Category.OTHER
        if category == Category.OTHER:
            draft = (
                "Thank you for your enquiry. Could you clarify the main service you need "
                "and the problem you want to solve? Please share your priorities so a person "
                "can review your request."
            )
        else:
            draft = (
                f"Thank you for your enquiry about {category.value.lower()} services. "
                "Please share your main goals, required features, and any constraints. "
                "A person will review the details before discussing scope or next steps."
            )
        return ProcessingResult(
            category=category,
            summary=" ".join(message.split())[:180],
            reply_draft=f"[DEMO DRAFT — manual review required]\n\n{draft}",
            clarification_questions=["What are your main goals and required features?"],
            faq_ids=[],
            needs_clarification=category == Category.OTHER,
            review_reason="Unknown or multiple matching services."
            if category == Category.OTHER
            else None,
        )
