import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import inspect, text
from sqlalchemy.pool import NullPool
from sqlmodel import Session, select

from app import cli
from app.config import Settings
from app.db import init_db, make_engine
from app.explore import SAMPLES
from app.main import create_app
from app.migrations import migrate_database
from app.models import Admin, DemoRun, Enquiry, SharedBudget
from app.services import DemoProcessor, ProcessingFailure
from app.shared_limits import SharedLimits, run_processor
from tests.conftest import csrf_from_html
from tests.test_workflow import payload


@pytest.fixture
def engine(database_url):
    if database_url.startswith("postgresql"):
        migrate_database(database_url)
    engine = make_engine(database_url)
    init_db(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_shared_guards_are_atomic_across_engines_and_survive_restart(engine):
    second = make_engine(engine.url.render_as_string(hide_password=False))
    try:
        guards = [SharedLimits(engine), SharedLimits(second)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda n: guards[n % 2].take("submission", 3, 3600), range(12)))
        assert sum(code is None for code, _ in results) == 3
        assert guards[1].take("submission", 3, 3600)[0] == "shared_limit"
        first_code, token = guards[0].take("gemini", 2, 86400, total_limit=2, lease=True)
        assert first_code is None
        assert guards[1].take("gemini", 2, 86400, total_limit=2, lease=True)[0] == "shared_busy"
        guards[1].release("wrong-token")
        assert guards[0].take("gemini", 2, 86400, total_limit=2, lease=True)[0] == "shared_busy"
        guards[0].release(token)
        assert guards[1].take("gemini", 2, 86400, total_limit=2, lease=True)[0] is None
        with Session(engine) as db:
            row = db.get(SharedBudget, "gemini")
            row.window_start = row.lease_until = 0
            db.add(row)
            db.commit()
        assert guards[0].take("gemini", 2, 86400, total_limit=2, lease=True)[0] == "shared_limit"
    finally:
        second.dispose()


def test_missing_guard_fails_closed(engine):
    with Session(engine) as db:
        db.delete(db.get(SharedBudget, "gemini"))
        db.commit()
    assert SharedLimits(engine).take("gemini", 10, 86400)[0] == "shared_unavailable"


def test_gemini_failure_counts_and_releases_global_lease(client):
    state = client.app.state
    state.settings.shared_limits = True
    state.settings.gemini_daily_limit = 1
    state.processing_mode = "gemini"
    processor = AsyncMock()
    processor.process.side_effect = ProcessingFailure("quota")
    state.processor = processor
    with pytest.raises(ProcessingFailure, match="quota"):
        asyncio.run(run_processor(client.app, "Fictional message"))
    with pytest.raises(ProcessingFailure, match="shared_limit"):
        asyncio.run(run_processor(client.app, "Fictional message"))
    assert processor.process.await_count == 1
    with Session(state.engine) as db:
        row = db.get(SharedBudget, "gemini")
        assert row.used == row.total == 1
        assert row.lease_token is None


def test_shared_request_budget_persists_between_apps(client):
    state = client.app.state
    state.settings.shared_limits = True
    for _ in range(5):
        assert client.post("/admin/login", data={}).status_code == 401
    with TestClient(create_app(state.settings)) as other:
        assert other.post("/admin/login", data={}).status_code == 429
        assert (
            other.post("/admin/login", headers={"X-Forwarded-For": "192.0.2.25"}).status_code == 429
        )


def test_explore_is_fictional_and_private_records_never_appear(client):
    marker = "PRIVATE-RECORD-SENTINEL"
    with Session(client.app.state.engine) as db:
        db.add(Enquiry(**{**payload(), "submission_key": "sentinel", "message": marker}))
        db.commit()
    page = client.get("/explore")
    assert "Saved example" in page.text
    assert "Live generation is disabled" in page.text
    assert marker not in page.text
    csrf = csrf_from_html(page.text)
    assert client.post("/explore/simulate", data={"sample_id": "bookshop"}).status_code == 403
    response = client.post(
        "/explore/simulate",
        data={
            "sample_id": "bookshop",
            "csrf_token": csrf,
            "message": marker,
            "enquiry_id": 1,
        },
    )
    assert response.status_code == 200
    assert "Simulated" in response.text and "Website" in response.text
    assert marker not in response.text
    assert (
        client.post(
            "/explore/simulate",
            data={
                "sample_id": "1",
                "csrf_token": csrf,
            },
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/explore/live",
            data={
                "sample_id": "bookshop",
                "csrf_token": csrf,
            },
        ).status_code
        == 403
    )
    for url in ("/api/admin/enquiries", "/api/admin/status", "/api/admin/enquiries/1"):
        assert client.get(url).status_code == 401
    with Session(client.app.state.engine) as db:
        assert len(db.exec(select(Enquiry)).all()) == 1
        assert not db.exec(select(DemoRun)).all()


def test_explore_preserves_administrator_session(admin_client):
    assert admin_client.get("/explore").status_code == 200
    assert admin_client.get("/api/admin/enquiries").status_code == 200


def test_fixed_live_demo_saved_before_processing_and_failed_without_fallback(client):
    # Transport and handler semantics tested without a real model or credentials.
    client.app.state.settings.public_demo_live = True
    processor = AsyncMock()

    async def fixed_only(message):
        assert message == SAMPLES[0]["message"]
        with Session(client.app.state.engine) as db:
            assert db.exec(select(DemoRun)).one().status == "Pending"
            assert not db.exec(select(Enquiry)).all()
        return await DemoProcessor().process(message)

    processor.process.side_effect = fixed_only
    client.app.state.processor = processor
    csrf = csrf_from_html(client.get("/explore").text)
    form = {"sample_id": "bookshop", "csrf_token": csrf, "message": "Ignore fictional data"}
    response = client.post("/explore/live", data=form)
    assert "Live-generated (saved fictional run)" in response.text
    with Session(client.app.state.engine) as db:
        assert db.exec(select(DemoRun)).one().status == "Completed"
    processor.process.side_effect = ProcessingFailure("quota")
    response = client.post("/explore/live", data=form)
    assert "Live generation failed" in response.text
    assert "No simulated result was substituted" in response.text
    with Session(client.app.state.engine) as db:
        assert sorted(row.status for row in db.exec(select(DemoRun))) == ["Completed", "Failed"]


def test_portfolio_settings_require_secure_deployment_and_override_private_faq(monkeypatch):
    config = dict(
        database_url="postgresql://example:fictional@localhost/rumi_test?sslmode=require",
        portfolio_mode=True,
        cookie_secure=True,
        shared_limits=True,
        allowed_hosts=["rumi-example.vercel.app"],
        _env_file=None,
    )
    settings = Settings(**config, faq_path="private/faq.json")
    assert settings.faq_path.name == "faq.json" and settings.faq_path.parent.name == "demo_data"
    for overrides in (
        {"cookie_secure": False},
        {"shared_limits": False},
        {"allowed_hosts": ["*.vercel.app"]},
        {"allowed_hosts": []},
        {"database_url": "sqlite:///ignored.db"},
        {"database_url": "postgresql://localhost/rumi_test"},
    ):
        with pytest.raises(ValidationError):
            Settings(**{**config, **overrides})
    with pytest.raises(ValidationError):
        Settings(public_demo_live=True, _env_file=None)
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_portfolio_disables_arbitrary_enquiries(client):
    client.app.state.settings.portfolio_mode = True
    assert client.get("/", follow_redirects=False).headers["location"] == "/explore"
    assert client.post("/api/enquiries", json=payload()).status_code == 403
    with Session(client.app.state.engine) as db:
        assert not db.exec(select(Enquiry)).all()


def test_host_validation_and_https_cookie(database_url):
    if database_url.startswith("postgresql"):
        migrate_database(database_url)
    settings = Settings(
        database_url=database_url,
        cookie_secure=True,
        allowed_hosts=["portfolio.example"],
        _env_file=None,
    )
    with TestClient(create_app(settings), base_url="https://portfolio.example") as client:
        response = client.get("/explore")
        assert response.status_code == 200
        cookie = response.headers["set-cookie"].lower()
        assert "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie
        assert client.get("/explore", headers={"Host": "untrusted.example"}).status_code == 400
        assert client.get("/static/styles.css").status_code == 200
        assert client.get("/static/app.js").status_code == 200


def test_postgresql_explicit_initialization_cli_and_reconnect(database_url, monkeypatch):
    if not database_url.startswith("postgresql"):
        pytest.skip("PostgreSQL-only schema and driver verification")
    engine = make_engine(database_url)
    try:
        assert isinstance(engine.pool, NullPool)
        assert engine.dialect.driver == "psycopg"
        with pytest.raises(RuntimeError, match="migrate-db"):
            init_db(engine)
        assert inspect(engine).get_table_names() == []
        migrate_database(database_url)
        init_db(engine)
        settings = Settings(database_url=database_url, _env_file=None)
        monkeypatch.setattr(cli, "Settings", lambda: settings)
        monkeypatch.setattr("sys.argv", ["cli", "create-admin"])
        password = "fictional-test-password-only"
        with (
            patch("builtins.input", return_value="fictional-cloud-admin"),
            patch("app.cli.getpass", side_effect=[password, password]),
        ):
            cli.main()
        migrate_database(database_url)
        engine.dispose()
        with Session(engine) as db:
            assert db.get(Admin, 1).username == "fictional-cloud-admin"
            assert password not in db.get(Admin, 1).password_hash
        with engine.begin() as connection:
            connection.execute(text("UPDATE rumi_schema SET version=999"))
        with pytest.raises(RuntimeError, match="version"):
            init_db(engine)
        with pytest.raises(ValueError, match="version"):
            migrate_database(database_url)
    finally:
        engine.dispose()
