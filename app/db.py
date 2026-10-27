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
    SQLModel.metadata.create_all(engine)


def get_db(request: Request):
    with Session(request.app.state.engine) as db:
        yield db
