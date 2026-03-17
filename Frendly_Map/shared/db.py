from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.migrations import assert_schema_version, run_migrations
from shared.models import Base


def _connect_args(db_url: str) -> dict:
    if db_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def create_db_engine(db_url: str):
    return create_engine(db_url, echo=False, future=True, connect_args=_connect_args(db_url))


def create_session_factory(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def db_context(SessionLocal):
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_schema(engine) -> None:
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)


def verify_schema(engine) -> None:
    assert_schema_version(engine)
