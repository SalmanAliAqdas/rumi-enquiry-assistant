import re
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth import password_hasher
from app.config import Settings
from app.main import create_app
from app.models import Admin


def csrf_from_html(html):
    return re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)


@pytest.fixture(autouse=True)
def forbid_live_models(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Live provider calls are forbidden in automated tests")

    async def async_blocked(*args, **kwargs):
        blocked()

    monkeypatch.setattr("google.genai.models.Models.generate_content", blocked)
    monkeypatch.setattr("google.genai.models.AsyncModels.generate_content", async_blocked)


@pytest.fixture
def client(tmp_path):
    faq = tmp_path / "faq.json"
    faq.write_text("[]", encoding="utf-8")
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'test.db'}",
            processor_mode="demo",
            gemini_api_key="",
            faq_path=faq,
            _env_file=None,
        )
    )
    with TestClient(app) as client:
        client.test_password = secrets.token_urlsafe(24)
        with Session(app.state.engine) as db:
            db.add(
                Admin(
                    username="test-admin", password_hash=password_hasher.hash(client.test_password)
                )
            )
            db.commit()
        yield client


@pytest.fixture
def admin_client(client):
    csrf = csrf_from_html(client.get("/admin/login").text)
    response = client.post(
        "/admin/login",
        data={"username": "test-admin", "password": client.test_password, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 303
    client.csrf = csrf_from_html(client.get("/admin").text)
    return client
