from contextlib import contextmanager

from shared.db import create_db_engine, create_session_factory, init_schema, verify_schema
from webapp.config import settings

engine = create_db_engine(settings.DB_URL)
SessionLocal = create_session_factory(engine)


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    # Ensure shared canonical models are loaded
    from shared.models import (  # noqa: F401
        Achievement,
        Location,
        LocationTag,
        Photo,
        Season,
        Tag,
        User,
        UserAchievement,
        WebAppPick,
    )

    init_schema(engine)
    verify_schema(engine)
