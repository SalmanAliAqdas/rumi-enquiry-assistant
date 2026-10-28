import os
import re
import secrets
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth import password_hasher
from app.config import Settings
from app.main import create_app
from app.models import Admin


@pytest.fixture(params=["sqlite"] + (["postgresql"] if os.getenv("TEST_POSTGRES_URL") else []))
def database_url(request, tmp_path):
    if request.param == "sqlite":
        yield f"sqlite:///{tmp_path / 'test.db'}"
        return
    import psycopg
    from psycopg import sql
    from sqlalchemy.engine import make_url

    target = make_url(os.environ["TEST_POSTGRES_URL"])
    if target.host not in {"localhost", "127.0.0.1", "::1"} or target.database != "rumi_test":
        pytest.fail("PostgreSQL tests require a localhost database named rumi_test")
    name = "rumi_test_" + uuid4().hex
    admin_url = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = target.set(database=name).render_as_string(hide_password=False)
    try:
        yield url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


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
def client(tmp_path, database_url):
    faq = tmp_path / "faq.json"
    faq.write_text("[]", encoding="utf-8")
    if database_url.startswith("postgresql"):
        from app.migrations import migrate_database

        migrate_database(database_url)
    app = create_app(
        Settings(
            database_url=database_url,
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
