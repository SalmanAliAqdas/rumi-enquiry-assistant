import secrets
import sqlite3
from pathlib import Path

import pytest
from sqlmodel import Session

from app.auth import password_hasher
from app.db import init_db, make_engine
from app.migrations import migrate_database
from app.models import Admin, Enquiry, WebSession


def phase_one_database(path: Path):
    password = secrets.token_urlsafe(24)
    password_hash = password_hasher.hash(password)
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE admin (id INTEGER PRIMARY KEY, username VARCHAR NOT NULL UNIQUE,
                                password_hash VARCHAR NOT NULL);
            CREATE TABLE websession (token_hash VARCHAR PRIMARY KEY, csrf_token VARCHAR NOT NULL,
                                     admin_id INTEGER, expires_at DATETIME NOT NULL);
            CREATE TABLE enquiry (
                id INTEGER PRIMARY KEY, reference VARCHAR NOT NULL UNIQUE,
                submission_key VARCHAR NOT NULL UNIQUE, name VARCHAR NOT NULL,
                email VARCHAR NOT NULL, message VARCHAR NOT NULL, category VARCHAR NOT NULL,
                summary VARCHAR NOT NULL, reply_draft VARCHAR NOT NULL,
                processing_mode VARCHAR NOT NULL, processing_status VARCHAR NOT NULL,
                workflow_status VARCHAR NOT NULL, created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
        """)
        db.execute("INSERT INTO admin VALUES (1, 'fictional-admin', ?)", (password_hash,))
        db.execute(
            "INSERT INTO websession VALUES "
            "('fictional-token-hash', 'fictional-csrf', 1, '2030-01-01 00:00:00')"
        )
        db.execute(
            "INSERT INTO enquiry VALUES (1, 'REA-LEGACY', 'legacy-submission', 'Example', "
            "'a@example.com', ?, 'WEBSITE', 'Legacy summary', 'Manually reviewed legacy draft', "
            "'demo', 'Completed', 'REVIEWED', '2026-01-01 00:00:00', '2026-01-02 00:00:00')",
            ("Original  message.\nPreserve spaces.",),
        )
    return password, password_hash


def test_populated_phase_one_migration_preserves_every_existing_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "legacy.db"
    password, password_hash = phase_one_database(target)
    url = f"sqlite:///{target}"
    with sqlite3.connect(target) as db:
        before = db.execute("SELECT * FROM enquiry").fetchone()
    engine = make_engine(url)
    try:
        with pytest.raises(RuntimeError, match="migrate-db"):
            init_db(engine)
    finally:
        engine.dispose()
    backup = migrate_database(url)
    assert backup.is_file()
    with sqlite3.connect(backup) as copy:
        assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert copy.execute("SELECT * FROM enquiry").fetchone() == before
        assert "candidate" not in {
            column[1] for column in copy.execute("PRAGMA table_info(enquiry)")
        }
    with sqlite3.connect(target) as db:
        assert db.execute("SELECT * FROM enquiry").fetchone()[: len(before)] == before
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
    engine = make_engine(url)
    try:
        init_db(engine)
        with Session(engine) as db:
            enquiry = db.get(Enquiry, 1)
            assert enquiry.workflow_status == "Reviewed"
            assert enquiry.processing_mode == "demo"
            assert enquiry.processing_status == "Completed"
            assert enquiry.reply_draft == "Manually reviewed legacy draft"
            assert enquiry.clarification_questions == []
            assert enquiry.faq_sources == []
            assert enquiry.candidate is None
            assert db.get(Admin, 1).password_hash == password_hash
            assert password_hasher.verify(password, db.get(Admin, 1).password_hash)
            assert db.get(WebSession, "fictional-token-hash").csrf_token == "fictional-csrf"
    finally:
        engine.dispose()
    # Repeating the command is data-preserving and makes a distinct backup.
    assert migrate_database(url) != backup


def test_migration_of_new_database_and_future_version_refusal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "new.db"
    assert migrate_database(f"sqlite:///{target}") is None
    with sqlite3.connect(target) as db:
        db.execute("PRAGMA user_version=999")
    with pytest.raises(ValueError, match="newer"):
        migrate_database(f"sqlite:///{target}")
    with sqlite3.connect(target) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 999
