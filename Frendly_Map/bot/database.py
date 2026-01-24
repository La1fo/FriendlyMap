# bot/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from bot.config import settings

engine = create_engine(settings.DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from bot.models.user import User
    from bot.models.location import Location
    from bot.models.tag import Tag
    from bot.models.location_tag import LocationTag
    from bot.models.achievement import Achievement
    from bot.models.season import Season
    Base.metadata.create_all(bind=engine)
