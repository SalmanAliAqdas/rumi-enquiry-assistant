from pathlib import Path

from fastapi import Request
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine


def make_engine(url: str):
    database = make_url(url).database
    if database and database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, connect_args={"check_same_thread": False})


def init_db(engine):
    from app.migrations import require_current_schema

    require_current_schema(engine)
    SQLModel.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA user_version=2")


def get_db(request: Request):
    with Session(request.app.state.engine) as db:
        yield db
