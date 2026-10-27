"""Only explicitly approved owner entries may become business knowledge."""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, StrictBool, TypeAdapter


class FAQEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=60, pattern=r"^[a-zA-Z0-9_-]+$")
    question: str = Field(min_length=1, max_length=300)
    answer: str = Field(min_length=1, max_length=1500)
    approved: StrictBool


def load_approved_faq(path: Path) -> list[FAQEntry]:
    if path.stat().st_size > 100_000:
        raise ValueError("FAQ file too large")
    entries = TypeAdapter(list[FAQEntry]).validate_python(
        json.loads(path.read_text(encoding="utf-8"))
    )
    if len(entries) > 100 or len({entry.id for entry in entries}) != len(entries):
        raise ValueError("FAQ IDs must be unique; at most 100 entries")
    return [entry for entry in entries if entry.approved is True]
