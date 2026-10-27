import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.limits import LocalBudget
from app.services import ProcessingFailure, ProcessingResult
from tests.conftest import csrf_from_html
from tests.test_gemini import FAKE_KEY, output
from tests.test_processing import configure_gemini
from tests.test_workflow import payload, submit


def test_budget_expiry_concurrency_and_reset():
    now = [0]
    budget = LocalBudget(limit=3, window=60, concurrent=2, clock=lambda: now[0])
    assert budget.enter() == (None, 0)
    assert budget.enter() == (None, 0)
    assert budget.enter()[0] == "local_busy"
    budget.leave()
    assert budget.enter() == (None, 0)
    budget.leave()
    budget.leave()
    assert budget.enter() == ("local_limit", 60)
    now[0] = 60
    assert budget.enter() == (None, 0)
    budget.leave()
    budget.reset()
    assert not budget.events


def test_login_budget_cannot_be_bypassed_with_new_session_or_forwarded_ip(client):
    now = [0]
    client.app.state.login_budget = LocalBudget(5, 300, clock=lambda: now[0])
    for _ in range(5):
        token = csrf_from_html(client.get("/admin/login").text)
        response = client.post(
            "/admin/login",
            data={
                "username": "not-an-admin",
                "password": "wrong",
                "csrf_token": token,
            },
        )
        assert response.status_code == 401
    token = csrf_from_html(client.get("/admin/login").text)
    credentials = {"username": "test-admin", "password": client.test_password, "csrf_token": token}
    response = client.post(
        "/admin/login", data=credentials, headers={"X-Forwarded-For": "192.0.2.1"}
    )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "300"
    assert client.test_password not in response.text
    now[0] = 301
    assert client.post("/admin/login", data=credentials, follow_redirects=False).status_code == 303
    assert not client.app.state.login_budget.events


def test_invalid_csrf_does_not_consume_login_budget(client):
    client.get("/admin/login")
    for _ in range(6):
        assert (
            client.post(
                "/admin/login",
                data={
                    "username": "test-admin",
                    "password": "wrong",
                    "csrf_token": "invalid",
                },
            ).status_code
            == 403
        )
    assert not client.app.state.login_budget.events


def test_model_limit_preserves_receipts_and_retries_after_window(admin_client):
    client = admin_client
    configure_gemini(client)
    now = [0]
    client.app.state.processing_budget = LocalBudget(6, 60, 2, clock=lambda: now[0])
    processor = AsyncMock()
    processor.process.return_value = ProcessingResult(**output(faq_ids=[]))
    client.app.state.processor = processor
    for _ in range(6):
        submit(client)
    data = payload()
    receipt = client.post("/api/enquiries", json=data)
    assert receipt.status_code == 201
    assert set(receipt.json()) == {"reference", "message"}
    assert client.post("/api/enquiries", json=data).json() == receipt.json()
    assert processor.process.await_count == 6
    row = client.get("/api/admin/enquiries/7").json()
    assert row["processing_error_code"] == "local_limit"
    assert row["processing_status"] == "Failed"
    assert row["message"] == data["message"]
    now[0] = 61
    retried = client.post(
        "/api/admin/enquiries/7/retry", json={}, headers={"X-CSRF-Token": client.csrf}
    )
    assert retried.status_code == 200
    assert retried.json()["candidate"]
    assert processor.process.await_count == 7
    assert client.app.state.processing_budget.active == 0


def test_model_busy_and_failure_release_slots(admin_client):
    client = admin_client
    configure_gemini(client)
    budget = client.app.state.processing_budget
    assert budget.enter()[0] is None
    assert budget.enter()[0] is None
    processor = AsyncMock()
    processor.process.side_effect = ProcessingFailure("quota")
    client.app.state.processor = processor
    submit(client)
    assert client.get("/api/admin/enquiries/1").json()["processing_error_code"] == "local_busy"
    processor.process.assert_not_awaited()
    budget.leave()
    budget.leave()
    assert (
        client.post(
            "/api/admin/enquiries/1/retry", json={}, headers={"X-CSRF-Token": client.csrf}
        ).status_code
        == 200
    )
    assert budget.active == 0
    assert client.get("/api/admin/enquiries/1").json()["processing_error_code"] == "quota"


def test_private_status_redacts_secrets_and_paths(admin_client, tmp_path):
    client = admin_client
    configure_gemini(client)
    faq = tmp_path / "owner-private-file-not-for-browser.json"
    client.app.state.settings.faq_path = faq
    faq.write_text("[]")
    response = client.get("/api/admin/status")
    assert response.status_code == 200
    status = response.json()
    assert status["mode"] == "gemini"
    assert status["key_configured"] is True
    assert status["approved_faq_count"] == 0
    assert "business knowledge is limited" in response.text
    for url in ("/api/admin/status", "/admin"):
        body = client.get(url).text
        assert FAKE_KEY not in body
        assert str(faq) not in body
        assert faq.name not in body
    public = client.get("/").text
    assert "Key configured" not in public
    assert status["model"] not in public
    faq.write_text(
        json.dumps(
            [
                {
                    "id": "fictional",
                    "question": "Fictional?",
                    "answer": "Fictional test only.",
                    "approved": True,
                }
            ]
        )
    )
    assert client.get("/api/admin/status").json()["approved_faq_count"] == 1
    faq.write_text("invalid JSON")
    failed = client.get("/api/admin/status").json()
    assert failed["approved_faq_count"] is None
    assert "FAQ file is missing or invalid" in failed["notes"][0]


def test_private_status_requires_authentication(client):
    assert client.get("/api/admin/status").status_code == 401
    client.get("/admin/login")
    assert client.get("/api/admin/status").status_code == 401


def test_stale_draft_save_is_rejected_without_overwriting(admin_client):
    client = admin_client
    submit(client)
    headers = {"X-CSRF-Token": client.csrf}
    body = {
        "reply_draft": "First reviewed fictional draft.",
        "workflow_status": "Reviewed",
        "expected_revision": 0,
    }
    first = client.patch("/api/admin/enquiries/1", json=body, headers=headers)
    assert first.status_code == 200
    stale = client.patch(
        "/api/admin/enquiries/1", json={**body, "reply_draft": "Stale tab edits"}, headers=headers
    )
    assert stale.status_code == 409
    saved = client.get("/api/admin/enquiries/1").json()
    assert saved["reply_draft"] == body["reply_draft"]
    assert saved["workflow_status"] == "Reviewed"
    assert saved["draft_revision"] == 1


def test_database_errors_hide_bound_private_parameters(client):
    with pytest.raises(IntegrityError) as exc, client.app.state.engine.begin() as connection:
        connection.execute(
            text("INSERT INTO admin (id, username, password_hash) VALUES (:id, :name, :hash)"),
            {"id": 1, "name": FAKE_KEY, "hash": "fictional-private-hash"},
        )
    assert FAKE_KEY not in str(exc.value)
    assert "fictional-private-hash" not in str(exc.value)


def test_oversized_page_number_is_validation_error(admin_client):
    response = admin_client.get("/api/admin/enquiries", params={"page": 2**80})
    assert response.status_code == 422
