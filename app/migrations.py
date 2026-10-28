"""Explicit SQLite backups/upgrades and transactional PostgreSQL revisions."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import inspect
from sqlmodel import SQLModel

from app import models  # noqa: F401 -- register tables even when invoked outside the web app
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
    if engine.dialect.name == "postgresql":
        from sqlalchemy import text

        with engine.connect() as connection:
            inspector = inspect(connection)
            if "rumi_schema" not in inspector.get_table_names():
                raise RuntimeError("Run python -m app.cli migrate-db before cloud startup")
            version = connection.execute(text("SELECT version FROM rumi_schema")).scalar_one()
            if version != 1:
                raise RuntimeError("Unsupported PostgreSQL schema version")
            for table in SQLModel.metadata.sorted_tables:
                if table.name not in inspector.get_table_names() or not {
                    c.name for c in table.columns
                } <= {c["name"] for c in inspector.get_columns(table.name)}:
                    raise RuntimeError("PostgreSQL schema is incomplete; migration required")
        return
    with engine.connect() as connection:
        if connection.exec_driver_sql("PRAGMA user_version").scalar_one() > 3:
            raise RuntimeError("Database schema is newer than this application")
    inspector = inspect(engine)
    if "enquiry" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("enquiry")}
        if not ADDITIONS.keys() <= columns:
            raise RuntimeError(
                "Database upgrade required: stop the app, then run python -m app.cli migrate-db"
            )
        if not {"sharedbudget", "demorun"} <= set(inspector.get_table_names()):
            raise RuntimeError("Database upgrade required: run python -m app.cli migrate-db")


def migrate_database(database_url: str) -> Path | None:
    engine = make_engine(database_url)
    try:
        if engine.dialect.name == "postgresql":
            migrate_postgresql(engine)
            return None
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
                if version > 3:
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
                connection.exec_driver_sql("PRAGMA user_version=3")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return backup
    finally:
        engine.dispose()


def migrate_postgresql(engine):
    """Initial PostgreSQL revision, transactional and serialized; no SQLite import."""
    from sqlalchemy import text

    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(748129031)"))
        tables = inspect(connection).get_table_names()
        if "rumi_schema" in tables:
            version = connection.execute(text("SELECT version FROM rumi_schema")).scalar_one()
            if version != 1:
                raise ValueError("Unsupported PostgreSQL schema version; database not changed")
        else:
            if tables:
                raise ValueError("Initial PostgreSQL migration requires an empty database")
            SQLModel.metadata.create_all(connection)
            connection.execute(text("CREATE TABLE rumi_schema (version INTEGER PRIMARY KEY)"))
            connection.execute(text("INSERT INTO rumi_schema VALUES (1)"))
        # Seed a fixed number of lock rows. Runtime never races to insert a budget.
        for scope in ("requests", "login", "submission", "gemini"):
            connection.execute(
                text(
                    "INSERT INTO sharedbudget (scope, window_start, used, total, lease_until) "
                    "VALUES (:scope, 0, 0, 0, 0) ON CONFLICT (scope) DO NOTHING"
                ),
                {"scope": scope},
            )
    require_current_schema(engine)
