from unittest.mock import AsyncMock

import pytest
from sqlmodel import Session, select

from app.models import Enquiry, ProcessingAttempt
from app.services import DemoProcessor, ProcessingFailure
from tests.conftest import csrf_from_html
from tests.test_workflow import payload

ENDPOINT = "/api/admin/enquiries"


def test_new_test_form_requires_administrator_and_csrf(client):
    assert client.get("/admin/enquiries/new", follow_redirects=False).status_code == 303
    assert client.post(ENDPOINT, json=payload()).status_code == 401
    csrf = csrf_from_html(client.get("/admin/login").text)
    assert client.post(ENDPOINT, json=payload(), headers={"X-CSRF-Token": csrf}).status_code == 401


def test_private_test_form_and_missing_csrf(admin_client):
    client = admin_client
    assert 'href="/admin/enquiries/new"' in client.get("/admin").text
    page = client.get("/admin/enquiries/new")
    assert page.status_code == 200
    assert "Fictional testing only" in page.text
    assert 'data-submit-url="/api/admin/enquiries"' in page.text
    assert csrf_from_html(page.text) == client.csrf
    for headers in ({}, {"X-CSRF-Token": "invalid"}):
        assert client.post(ENDPOINT, json=payload(), headers=headers).status_code == 403
    with Session(client.app.state.engine) as db:
        assert not db.exec(select(Enquiry)).all()


def test_portfolio_private_gemini_save_first_and_idempotence(admin_client):
    client = admin_client
    state = client.app.state
    state.settings.portfolio_mode = True
    state.settings.shared_limits = True
    state.processing_mode = "gemini"
    message = "  A fictional private website.\nKeep  inner spaces for review.  "
    data = payload(message=message, name="Fictional reviewer")

    async def process(message):
        with Session(state.engine) as db:
            row = db.exec(select(Enquiry)).one()
            assert row.message == data["message"].strip()
            assert row.processing_status == "Processing"
            assert row.reference.startswith("REA-TEST-")
        # Prove no transaction holds the saved row while the provider is called.
        with state.engine.connect() as connection:
            connection.exec_driver_sql(
                "BEGIN IMMEDIATE"
                if connection.dialect.name == "sqlite"
                else "SELECT id FROM enquiry FOR UPDATE NOWAIT"
            )
            connection.rollback()
        return await DemoProcessor().process(message)

    processor = AsyncMock()
    processor.process.side_effect = process
    state.processor = processor
    headers = {"X-CSRF-Token": client.csrf}
    response = client.post(ENDPOINT, json=data, headers=headers)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["processing_mode"] == "gemini" and saved["processing_status"] == "Completed"
    assert saved["reply_draft"] and saved["workflow_status"] == "New"
    assert saved["message"] == message.strip()
    assert client.post(ENDPOINT, json=data, headers=headers).json() == saved
    assert (
        client.post(ENDPOINT, json={**data, "name": "Changed"}, headers=headers).status_code == 409
    )
    assert processor.process.await_count == 1
    assert "Fictional test enquiry" in client.get(f"/admin/enquiries/{saved['id']}").text
    assert "Fictional test enquiry" in client.get("/admin").text
    edit = client.patch(
        f"{ENDPOINT}/{saved['id']}",
        headers=headers,
        json={
            "reply_draft": "Manually reviewed fictional draft.",
            "workflow_status": "Reviewed",
            "expected_revision": saved["draft_revision"],
        },
    )
    assert edit.status_code == 200 and edit.json()["workflow_status"] == "Reviewed"
    assert "Fictional reviewer" not in client.get("/explore").text
    assert client.post("/api/enquiries", json=payload()).status_code == 403
    with Session(state.engine) as db:
        assert len(db.exec(select(Enquiry)).all()) == 1
        assert len(db.exec(select(ProcessingAttempt)).all()) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "invalid"},
        {"name": "   "},
        {"name": "x" * 101},
        {"message": "too short"},
        {"message": "x" * 3001},
        {"submission_key": "invalid"},
        {"reference": "injected"},
    ],
)
def test_private_submission_uses_existing_validation(admin_client, changes):
    response = admin_client.post(
        ENDPOINT, json=payload(**changes), headers={"X-CSRF-Token": admin_client.csrf}
    )
    assert response.status_code == 422
    assert all("input" not in error for error in response.json()["detail"])
    with Session(admin_client.app.state.engine) as db:
        assert not db.exec(select(Enquiry)).all()


@pytest.mark.parametrize("failure", ["quota", "shared_limit", "shared_unavailable"])
def test_private_failures_preserve_saved_record_without_fallback(admin_client, failure):
    client = admin_client
    state = client.app.state
    state.processing_mode = "gemini"
    state.settings.shared_limits = True
    processor = AsyncMock()
    processor.process.side_effect = ProcessingFailure("quota")
    state.processor = processor
    if failure == "shared_limit":
        state.settings.gemini_daily_limit = 0
    elif failure == "shared_unavailable":
        from app.models import SharedBudget

        with Session(state.engine) as db:
            db.delete(db.get(SharedBudget, "gemini"))
            db.commit()
    data = payload()
    headers = {"X-CSRF-Token": client.csrf}
    response = client.post(ENDPOINT, json=data, headers=headers)
    assert response.status_code == 201
    row = response.json()
    assert row["processing_status"] == "Failed"
    assert row["processing_error_code"] == failure
    assert row["message"] == data["message"] and row["reply_draft"] == ""
    assert "Processing needs attention" in client.get(f"/admin/enquiries/{row['id']}").text
    assert client.post(ENDPOINT, json=data, headers=headers).json() == row
    assert processor.process.await_count == (1 if failure == "quota" else 0)


def test_private_submission_uses_shared_request_allowance(admin_client):
    client = admin_client
    client.app.state.settings.shared_limits = True
    guard = client.app.state.shared_limits
    for _ in range(20):
        assert guard.take("submission", 20, 3600)[0] is None
    response = client.post(ENDPOINT, json=payload(), headers={"X-CSRF-Token": client.csrf})
    assert response.status_code == 429
    with Session(client.app.state.engine) as db:
        assert not db.exec(select(Enquiry)).all()
