"""Explicit, backed-up SQLite upgrade; startup never upgrades an existing schema."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import inspect
from sqlmodel import SQLModel

from app.db import make_engine

ADDITIONS = {
    "clarification_questions": "JSON NOT NULL DEFAULT '[]'",
    "faq_sources": "JSON NOT NULL DEFAULT '[]'",
    "needs_clarification": "BOOLEAN NOT NULL DEFAULT 0",
    "review_reason": "TEXT",
    "processing_error_code": "TEXT",
    "processing_error": "TEXT",
    "processing_started_at": "DATETIME",
    "processing_token": "TEXT",
    "candidate": "JSON",
    "draft_revision": "INTEGER NOT NULL DEFAULT 0",
}


def require_current_schema(engine):
    with engine.connect() as connection:
        if connection.exec_driver_sql("PRAGMA user_version").scalar_one() > 2:
            raise RuntimeError("Database schema is newer than this application")
    inspector = inspect(engine)
    if "enquiry" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("enquiry")}
        if not ADDITIONS.keys() <= columns:
            raise RuntimeError(
                "Database upgrade required: stop the app, then run python -m app.cli migrate-db"
            )


def migrate_database(database_url: str) -> Path | None:
    engine = make_engine(database_url)
    try:
        database = engine.url.database
        if not database or database == ":memory:":
            raise ValueError("Migration requires a file-backed SQLite database")
        source = Path(database).resolve()
        backup = None
        if source.exists():
            backup_dir = Path("backups")
            backup_dir.mkdir(exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            backup = backup_dir / f"rumi-{stamp}-{uuid4().hex[:8]}.sqlite3"
            # SQLite's backup API also includes committed WAL data.
            with sqlite3.connect(source) as original, sqlite3.connect(backup) as copy:
                original.backup(copy)
                if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Backup integrity check failed; database not changed")
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
                if version > 2:
                    raise ValueError("Database is newer than this application")
                inspector = inspect(connection)
                if "enquiry" in inspector.get_table_names():
                    columns = {column["name"] for column in inspector.get_columns("enquiry")}
                    for name, definition in ADDITIONS.items():
                        if name not in columns:
                            connection.exec_driver_sql(
                                f'ALTER TABLE enquiry ADD COLUMN "{name}" {definition}'
                            )
                SQLModel.metadata.create_all(connection)
                connection.exec_driver_sql("PRAGMA user_version=2")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return backup
    finally:
        engine.dispose()
