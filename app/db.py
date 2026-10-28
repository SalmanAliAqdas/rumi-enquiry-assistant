from pathlib import Path

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine


def make_engine(url: str):
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url, connect_args={"check_same_thread": False}, hide_parameters=True)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("Unsupported database")
    engine = create_engine(
        parsed.set(drivername="postgresql+psycopg"),
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 10,
            "prepare_threshold": None,
        },
        hide_parameters=True,
    )

    @event.listens_for(engine, "begin")
    def transaction_timeouts(connection):
        # Transaction-local settings work with Neon's transaction pooler.
        connection.exec_driver_sql("SET LOCAL statement_timeout = '10s'")
        connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")

    return engine


def init_db(engine):
    from app.migrations import require_current_schema

    require_current_schema(engine)
    if engine.dialect.name == "postgresql":
        return  # Cloud DDL is CLI-only, never a cold-start side effect.
    SQLModel.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA user_version=3")
        for scope in ("requests", "login", "submission", "gemini"):
            connection.exec_driver_sql(
                "INSERT OR IGNORE INTO sharedbudget "
                "(scope, window_start, used, total, lease_until) VALUES (?, 0, 0, 0, 0)",
                (scope,),
            )


def get_db(request: Request):
    with Session(request.app.state.engine) as db:
        yield db
