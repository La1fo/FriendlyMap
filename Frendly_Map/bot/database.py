# bot/database.py
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from bot.config import settings
from bot.models.base import Base

connect_args = {}
if settings.DB_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.DB_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

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
    from bot.models.user import User  # noqa: F401
    from bot.models.location import Location  # noqa: F401
    from bot.models.photo import Photo  # noqa: F401
    from bot.models.tag import Tag  # noqa: F401
    from bot.models.location_tag import LocationTag  # noqa: F401
    from bot.models.achievement import Achievement  # noqa: F401
    from bot.models.season import Season  # noqa: F401
    from bot.models.user_achievement import UserAchievement  # noqa: F401
    Base.metadata.create_all(bind=engine)
