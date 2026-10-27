import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlmodel import Session, select

from app.gemini import build_processor
from app.models import Enquiry, ProcessingAttempt, utcnow
from app.processing import process_enquiry
from app.services import ProcessingFailure, ProcessingResult
from tests.test_gemini import FAKE_KEY, mocked_provider, output, response, settings
from tests.test_workflow import payload, submit


def configure_gemini(client, **changes):
    configured = settings(**changes)
    client.app.state.settings = configured
    client.app.state.processing_mode = "gemini"
    client.app.state.processing_model = configured.gemini_model
    client.app.state.processor, client.app.state.processing_timeout = build_processor(configured)


@pytest.mark.parametrize(
    "code",
    ["missing_key", "timeout", "quota", "authentication", "provider", "blocked", "invalid_output"],
)
def test_processing_failures_preserve_receipt_and_do_not_retry(client, code):
    client.app.state.processor = AsyncMock()
    client.app.state.processor.process.side_effect = ProcessingFailure(code)
    data = payload()
    first = client.post("/api/enquiries", json=data)
    assert first.status_code == 201
    assert set(first.json()) == {"reference", "message"}
    assert code not in first.text
    assert client.post("/api/enquiries", json=data).json() == first.json()
    assert client.app.state.processor.process.await_count == 1
    with Session(client.app.state.engine) as db:
        row = db.exec(select(Enquiry)).one()
        assert row.reference == first.json()["reference"]
        assert row.message == data["message"]
        assert row.processing_status == "Failed"
        assert row.processing_error_code == code
        assert row.reply_draft == ""


def test_missing_key_real_factory_still_saves(client):
    configure_gemini(client, gemini_api_key="")
    receipt = submit(client)
    with Session(client.app.state.engine) as db:
        row = db.exec(select(Enquiry)).one()
        assert row.reference == receipt["reference"]
        assert row.processing_status == "Failed"
        assert row.processing_mode == "gemini"
        assert row.processing_error_code == "missing_key"


def test_request_timeout_is_bounded_and_receipt_saved(client):
    async def slow(message):
        await asyncio.sleep(5)

    client.app.state.processor = AsyncMock()
    client.app.state.processor.process.side_effect = slow
    client.app.state.processing_timeout = 0.02
    submit(client)
    with Session(client.app.state.engine) as db:
        assert db.exec(select(Enquiry)).one().processing_error_code == "timeout"


def test_sanitized_unexpected_exception_and_private_diagnostics(admin_client):
    client = admin_client
    client.app.state.processor = AsyncMock()
    client.app.state.processor.process.side_effect = RuntimeError(
        FAKE_KEY + " raw provider details"
    )
    receipt = submit(client)
    assert FAKE_KEY not in str(receipt)
    item = client.get("/api/admin/enquiries").json()["items"][0]
    detail = client.get(f"/admin/enquiries/{item['id']}")
    assert "Processing needs attention" in detail.text
    assert "retry" in detail.text.lower()
    assert FAKE_KEY not in detail.text
    assert "raw provider details" not in detail.text
    assert item["processing_error_code"] == "provider"


def test_retry_candidate_manual_preservation_and_explicit_apply(admin_client):
    client = admin_client
    configure_gemini(client, gemini_api_key="")
    submit(client)
    item = client.get("/api/admin/enquiries").json()["items"][0]
    url = f"/api/admin/enquiries/{item['id']}"
    headers = {"X-CSRF-Token": client.csrf}
    change = {"reply_draft": "Manually reviewed fictional draft.", "workflow_status": "Reviewed"}
    assert client.patch(url, json=change, headers=headers).status_code == 200
    configure_gemini(client)
    context, provider = mocked_provider(response())
    with context:
        assert client.post(url + "/retry", json={}).status_code == 403
        result = client.post(url + "/retry", json={}, headers=headers)
    assert result.status_code == 200, result.text
    row = result.json()
    assert row["processing_status"] == "Completed"
    assert row["reply_draft"] == change["reply_draft"]
    assert row["workflow_status"] == "Reviewed"
    assert row["candidate"]["summary"] == output()["summary"]
    assert provider.aio.models.generate_content.await_count == 1
    data = {"candidate_id": row["candidate"]["id"], "draft_revision": row["draft_revision"]}
    assert client.post(url + "/apply-candidate", json=data).status_code == 403
    # Changes made after the candidate page was loaded invalidate its revision.
    assert (
        client.patch(url, json={**change, "workflow_status": "Closed"}, headers=headers).status_code
        == 200
    )
    assert client.post(url + "/apply-candidate", json=data, headers=headers).status_code == 409
    data["draft_revision"] = client.get(url).json()["draft_revision"]
    applied = client.post(url + "/apply-candidate", json=data, headers=headers)
    assert applied.status_code == 200, applied.text
    assert applied.json()["workflow_status"] == "Closed"
    assert applied.json()["reply_draft"] != change["reply_draft"]
    assert applied.json()["candidate"] is None
    assert applied.json()["faq_sources"][0]["id"] == "fictional-web"
    assert client.post(url + "/apply-candidate", json=data, headers=headers).status_code == 409
    assert client.post(url + "/retry", json={}, headers=headers).status_code == 409
    with Session(client.app.state.engine) as db:
        attempts = db.exec(select(ProcessingAttempt)).all()
        assert [attempt.status for attempt in attempts] == ["Failed", "Completed"]


def test_anonymous_retry_and_candidate_are_protected(client):
    submit(client)
    for action in ("retry", "apply-candidate"):
        assert client.post(f"/api/admin/enquiries/1/{action}", json={}).status_code == 401


def test_duplicate_submission_during_processing_and_no_open_transaction(client):
    entered, release = threading.Event(), threading.Event()

    async def slow(message):
        entered.set()
        while not release.is_set():
            await asyncio.sleep(0.01)
        return ProcessingResult(**output(faq_ids=[]))

    client.app.state.processor = AsyncMock()
    client.app.state.processor.process.side_effect = slow
    data = payload()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(client.post, "/api/enquiries", json=data)
        try:
            assert entered.wait(3)
            # A different connection can acquire a write transaction while the
            # provider is in flight, and sees the committed original enquiry.
            with client.app.state.engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                assert connection.exec_driver_sql("SELECT COUNT(*) FROM enquiry").scalar_one() == 1
                connection.rollback()
            duplicate = client.post("/api/enquiries", json=data)
            assert duplicate.status_code == 201
            with Session(client.app.state.engine) as db:
                row = db.exec(select(Enquiry)).one()
                assert row.processing_status == "Processing"
                assert not asyncio.run(process_enquiry(client.app, row.id))
        finally:
            release.set()
        assert future.result(timeout=5).json() == duplicate.json()
    assert client.app.state.processor.process.await_count == 1


def test_manual_edit_during_first_processing_becomes_candidate(admin_client):
    client = admin_client
    entered, release = threading.Event(), threading.Event()

    async def slow(message):
        entered.set()
        while not release.is_set():
            await asyncio.sleep(0.01)
        return ProcessingResult(**output(faq_ids=[]))

    client.app.state.processor = AsyncMock()
    client.app.state.processor.process.side_effect = slow
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(client.post, "/api/enquiries", json=payload())
        try:
            assert entered.wait(3)
            row = client.get("/api/admin/enquiries").json()["items"][0]
            result = client.patch(
                f"/api/admin/enquiries/{row['id']}",
                json={
                    "reply_draft": "Human draft written during processing.",
                    "workflow_status": "Reviewed",
                },
                headers={"X-CSRF-Token": client.csrf},
            )
            assert result.status_code == 200
        finally:
            release.set()
        assert future.result(timeout=5).status_code == 201
    item = client.get("/api/admin/enquiries").json()["items"][0]
    assert item["reply_draft"] == "Human draft written during processing."
    assert item["workflow_status"] == "Reviewed"
    assert item["candidate"] is not None


def test_stale_claim_can_be_recovered_without_old_result_winning(client):
    with Session(client.app.state.engine) as db:
        row = Enquiry(
            submission_key="stale-test",
            name="Example",
            email="a@example.com",
            message="Fictional request for a website.",
            processing_status="Processing",
            processing_token="old-token",
            processing_started_at=utcnow() - timedelta(seconds=100),
        )
        db.add(row)
        db.commit()
        enquiry_id = row.id
    assert asyncio.run(process_enquiry(client.app, enquiry_id))
    with Session(client.app.state.engine) as db:
        row = db.get(Enquiry, enquiry_id)
        assert row.processing_status == "Completed"
        assert row.candidate


def test_generated_content_and_candidate_are_escaped(admin_client):
    client = admin_client
    client.app.state.processor = AsyncMock()
    client.app.state.processor.process.side_effect = ProcessingFailure("quota")
    submit(client)
    client.app.state.processor.process.side_effect = None
    script = '<script>alert("fictional")</script>'
    client.app.state.processor.process.return_value = ProcessingResult(
        **output(
            summary=script,
            clarification_questions=[script],
            review_reason=script,
            faq_ids=[],
            reply_draft="</textarea>" + script,
        )
    )
    headers = {"X-CSRF-Token": client.csrf}
    assert client.post("/api/admin/enquiries/1/retry", json={}, headers=headers).status_code == 200
    html = client.get("/admin/enquiries/1").text
    assert script not in html
    assert "&lt;script&gt;" in html
    assert "&lt;/textarea&gt;" in html
