"""Explicit safe projections for private review; never expose Settings or paths."""

import re

from app.gemini import UnavailableProcessor
from app.knowledge import load_approved_faq
from app.schemas import ConfigurationStatus


def configuration_status(app) -> ConfigurationStatus:
    settings = app.state.settings
    notes = []
    try:
        count = len(load_approved_faq(settings.faq_path))
    except (OSError, ValueError):
        count = None
        notes.append(
            "FAQ file is missing or invalid. Follow the owner guide to set up valid knowledge."
        )
    if count == 0:
        notes.append(
            "No approved FAQs: enquiry analysis is available, but business knowledge is limited. "
            "Review and approve verified facts before expecting business answers."
        )
    if isinstance(app.state.processor, UnavailableProcessor):
        notes.append("Processing configuration needs attention. Check server settings and restart.")
    if app.state.processing_mode == "demo":
        notes.append("Demo processing uses fixed examples and does not consult business knowledge.")
    return ConfigurationStatus(
        mode=app.state.processing_mode,
        model=settings.gemini_model
        if re.fullmatch(r"gemini-[a-z0-9.-]{1,80}", settings.gemini_model)
        else None,
        key_configured=bool(settings.gemini_api_key.get_secret_value().strip()),
        approved_faq_count=count,
        notes=notes,
    )


def next_action(enquiry) -> str:
    if enquiry.processing_status == "Failed":
        return "Read the processing diagnostic and original message, then retry if appropriate."
    if enquiry.processing_status == "Processing":
        return "Wait for processing. An interrupted attempt can be recovered after 90 seconds."
    if enquiry.processing_status == "Pending":
        return "Retry processing, or write a draft manually."
    if enquiry.candidate:
        return "Review the new candidate and its sources before applying it to the saved draft."
    if not enquiry.reply_draft:
        return "Write a reply draft for manual review."
    if enquiry.workflow_status == "Closed":
        return "This enquiry is closed. No reply has been sent by this application."
    if enquiry.workflow_status == "Reviewed":
        return "Check the saved draft before copying it. Close the enquiry when review is finished."
    return "Review the needs, sources, and saved draft, then mark the enquiry Reviewed."
