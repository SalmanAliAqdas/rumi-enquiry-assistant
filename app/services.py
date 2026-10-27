"""A small replaceable interface. Phase 1 never makes external requests."""

import re
from dataclasses import dataclass
from typing import Protocol

from app.models import Category

DEMO_LABEL = "Demo processing — no AI model connected."


@dataclass(frozen=True)
class ProcessingResult:
    category: Category
    summary: str
    reply_draft: str


class Processor(Protocol):
    def process(self, message: str) -> ProcessingResult: ...


class DemoProcessor:
    keywords = {
        Category.WEBSITE: {"website", "websites", "web", "landing"},
        Category.MOBILE: {"mobile", "android", "ios", "iphone"},
        Category.AUTOMATION: {"automation", "automate", "workflow", "workflows"},
    }

    def process(self, message: str) -> ProcessingResult:
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
        )
