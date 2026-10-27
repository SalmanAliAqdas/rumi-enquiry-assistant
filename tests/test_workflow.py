import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from app.auth import COOKIE, hash_token
from app.models import Enquiry, WebSession, utcnow
from app.services import DEMO_LABEL, DemoProcessor
from tests.conftest import csrf_from_html


def payload(**changes):
    return {
        "name": "Alex Example",
        "email": "alex@example.com",
        "message": "We need a website for a fictional community project.",
        "submission_key": str(uuid4()),
        **changes,
    }


def submit(client, **changes):
    response = client.post("/api/enquiries", json=payload(**changes))
    assert response.status_code == 201, response.text
    return response.json()


def test_submission_persists_and_retries_once(client):
    message = "  A fictional website idea.\nKeep  inner spaces.  "
    data = payload(message=message)
    first = client.post("/api/enquiries", json=data)
    assert first.status_code == 201
    assert set(first.json()) == {"reference", "message"}
    assert first.json()["reference"].startswith("REA-")
    assert client.post("/api/enquiries", json=data).json() == first.json()
    assert client.post("/api/enquiries", json={**data, "name": "Changed"}).status_code == 409
    with Session(client.app.state.engine) as db:
        rows = db.exec(select(Enquiry)).all()
        assert len(rows) == 1
        assert rows[0].message == message.strip()
        assert rows[0].processing_mode == "demo"
        assert rows[0].category == "Website"
        assert rows[0].workflow_status == "New"
    # A second app instance reads the same SQLite file (persistence across restart).
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(client.app.state.settings)) as restarted:
        assert restarted.post("/api/enquiries", json=data).json() == first.json()


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "invalid"},
        {"message": ""},
        {"message": "  "},
        {"message": "too short"},
        {"message": "x" * 3001},
        {"name": " "},
        {"name": "n" * 101},
        {"email": "a" * 260 + "@example.com"},
        {"submission_key": "invalid"},
    ],
)
def test_invalid_submissions(client, changes):
    response = client.post("/api/enquiries", json=payload(**changes))
    assert response.status_code == 422
    assert "input" not in response.text
    with Session(client.app.state.engine) as db:
        assert not db.exec(select(Enquiry)).all()


def test_request_size_guard(client):
    assert client.post("/api/enquiries", content="x" * 24001).status_code == 413


@pytest.mark.parametrize("path", ["/api/admin/enquiries", "/api/admin/enquiries/1"])
def test_anonymous_private_api(client, path):
    submit(client)
    assert client.get(path).status_code == 401
    assert client.patch(
        path, json={"reply_draft": "secret", "workflow_status": "Closed"}
    ).status_code in {401, 405}


def test_anonymous_pages(client):
    for path in ("/admin", "/admin/enquiries/1"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/admin/login"
    # Pre-login sessions have no private access.
    client.get("/admin/login")
    assert client.get("/api/admin/enquiries").status_code == 401
    assert client.patch("/api/admin/enquiries/1", json={}).status_code == 401


def test_login_csrf_and_failure(client):
    page = client.get("/admin/login")
    token = csrf_from_html(page.text)
    assert "HttpOnly" in page.headers["set-cookie"]
    assert "SameSite=strict" in page.headers["set-cookie"]
    assert "Max-Age=3600" in page.headers["set-cookie"]
    credentials = {"username": "test-admin", "password": client.test_password}
    assert client.post("/admin/login", data=credentials).status_code == 403
    response = client.post(
        "/admin/login", data={**credentials, "password": "wrong", "csrf_token": token}
    )
    assert response.status_code == 401
    assert "incorrect" in response.text
    assert client.get("/api/admin/enquiries").status_code == 401


def test_session_rotation_expiry_and_logout(client):
    token = csrf_from_html(client.get("/admin/login").text)
    before = client.cookies.get(COOKIE)
    response = client.post(
        "/admin/login",
        data={"username": "test-admin", "password": client.test_password, "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    after = client.cookies.get(COOKIE)
    assert before != after
    with Session(client.app.state.engine) as db:
        assert db.get(WebSession, hash_token(before)) is None
    csrf = csrf_from_html(client.get("/admin").text)
    assert client.post("/admin/logout", follow_redirects=False).status_code == 403
    assert (
        client.post("/admin/logout", data={"csrf_token": csrf}, follow_redirects=False).status_code
        == 303
    )
    assert client.get("/api/admin/enquiries").status_code == 401
    client.cookies.set(COOKIE, after, domain="testserver.local", path="/")
    assert client.get("/api/admin/enquiries").status_code == 401


def test_expired_and_forged_sessions(admin_client):
    client = admin_client
    with Session(client.app.state.engine) as db:
        session = db.get(WebSession, hash_token(client.cookies.get(COOKIE)))
        session.expires_at = utcnow() - timedelta(seconds=1)
        db.add(session)
        db.commit()
    assert client.get("/api/admin/enquiries").status_code == 401
    client.cookies.clear()
    client.cookies.set(COOKIE, "forged")
    assert client.get("/api/admin/enquiries").status_code == 401


def test_edit_requires_csrf_and_persists(admin_client):
    client = admin_client
    submit(client)
    item = client.get("/api/admin/enquiries").json()["items"][0]
    url = f"/api/admin/enquiries/{item['id']}"
    change = {
        "reply_draft": "Edited fictional draft for manual review.",
        "workflow_status": "Reviewed",
    }
    assert client.patch(url, json=change).status_code == 403
    assert client.patch(url, json=change, headers={"X-CSRF-Token": "bad"}).status_code == 403
    headers = {"X-CSRF-Token": client.csrf}
    response = client.patch(url, json=change, headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == item["message"]
    assert response.json()["updated_at"].endswith("+00:00")
    assert client.get(url).json()["reply_draft"] == change["reply_draft"]
    assert (
        client.patch(
            url, json={**change, "workflow_status": "Invalid"}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.patch(url, json={**change, "reply_draft": "  "}, headers=headers).status_code == 422
    )
    assert (
        client.patch(url, json={**change, "workflow_status": "Closed"}, headers=headers).status_code
        == 200
    )
    assert client.get(url).json()["workflow_status"] == "Closed"
    assert client.get("/api/admin/enquiries/99999").status_code == 404


def test_search_filters_pagination_and_counts(admin_client):
    client = admin_client
    submit(
        client,
        name="Fictional Website",
        message="A fictional website project for a learning exercise.",
    )
    submit(
        client,
        name="Fictional Mobile",
        message="A fictional mobile project for a learning exercise.",
    )
    submit(
        client,
        name="Fictional Automation",
        message="A fictional automation project for a learning exercise.",
    )
    results = client.get("/api/admin/enquiries", params={"page_size": 2}).json()
    assert results["total"] == 3
    assert results["counts"] == {"New": 3, "Reviewed": 0, "Closed": 0}
    assert results["items"][0]["name"] == "Fictional Automation"
    assert (
        client.get("/api/admin/enquiries", params={"page_size": 2, "page": 2}).json()["items"][0][
            "name"
        ]
        == "Fictional Website"
    )
    assert (
        client.get(
            "/api/admin/enquiries",
            params={"q": "mobile", "category": "Mobile application", "status": "New"},
        ).json()["total"]
        == 1
    )
    assert client.get("/api/admin/enquiries", params={"q": "%"}).json()["total"] == 0
    assert client.get("/api/admin/enquiries", params={"status": "Closed"}).json()["total"] == 0
    assert client.get("/api/admin/enquiries", params={"page": 0}).status_code == 422
    assert client.get("/api/admin/enquiries", params={"category": "bad"}).status_code == 422
    assert client.get("/admin?q=Fictional&category=&status=").status_code == 200
    assert "Next" in client.get("/admin?page_size=2").text


def test_safe_html_and_demo_labelling(admin_client):
    client = admin_client
    script = '<script>alert("fictional")</script> website learning example'
    submit(client, name="<b>Example</b>", message=script)
    item = client.get("/api/admin/enquiries").json()["items"][0]
    detail = client.get(f"/admin/enquiries/{item['id']}")
    assert script not in detail.text
    assert "&lt;script&gt;" in detail.text
    assert "&lt;b&gt;Example&lt;/b&gt;" in detail.text
    assert DEMO_LABEL in detail.text
    assert "manual review" in detail.text.lower()
    evil_draft = '</textarea><script>alert("test")</script>'
    client.patch(
        f"/api/admin/enquiries/{item['id']}",
        json={"reply_draft": evil_draft, "workflow_status": "New"},
        headers={"X-CSRF-Token": client.csrf},
    )
    html = client.get(f"/admin/enquiries/{item['id']}").text
    assert evil_draft not in html
    assert "&lt;/textarea&gt;" in html
    assert "frame-ancestors 'none'" in detail.headers["content-security-policy"]
    assert detail.headers["cache-control"] == "no-store"
    assert DEMO_LABEL in client.get("/").text


@pytest.mark.parametrize(
    "message",
    [
        "Please help with this fictional project.",
        "We want a website and mobile app for our example.",
        "websiteish is not a matching keyword.",
    ],
)
def test_ambiguous_or_unknown_gets_clarification(message):
    result = asyncio.run(DemoProcessor().process(message))
    assert result.category == "Other / needs clarification"
    assert "clarify" in result.reply_draft
    assert "DEMO DRAFT" in result.reply_draft
    assert result == asyncio.run(DemoProcessor().process(message))


def test_host_validation(client):
    assert client.get("/", headers={"host": "untrusted.example.com"}).status_code == 400
