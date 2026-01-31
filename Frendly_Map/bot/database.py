# bot/database.py
from contextlib import contextmanager
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from bot.config import settings
from bot.models.base import Base

connect_args = {}
if settings.DB_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DB_URL,
    echo=False,
    future=True,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
)
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
    from bot.models.moderation_log import ModerationLog  # noqa: F401
    from bot.models.faq_item import FaqItem  # noqa: F401
    from bot.models.ticket import Ticket  # noqa: F401
    from bot.models.ticket_message import TicketMessage  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_role_column()
    _ensure_location_columns()


def _ensure_role_column():
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    columns = [col["name"] for col in inspector.get_columns("users")]
    if "role" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'"))


def _ensure_location_columns():
    inspector = inspect(engine)
    if "locations" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("locations")}
    statements = []
    if "is_deleted" not in columns:
        statements.append("ALTER TABLE locations ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE")
    if "deleted_at" not in columns:
        statements.append("ALTER TABLE locations ADD COLUMN deleted_at TIMESTAMP")
    if "deleted_by" not in columns:
        statements.append("ALTER TABLE locations ADD COLUMN deleted_by INTEGER")
    if "deleted_reason" not in columns:
        statements.append("ALTER TABLE locations ADD COLUMN deleted_reason TEXT")
    if not statements:
        return
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
