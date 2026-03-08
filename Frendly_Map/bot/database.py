# bot/database.py
from contextlib import contextmanager
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from bot.config import settings
from bot.models.base import Base

logger = logging.getLogger(__name__)

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


def _migrate_postgres_ids_to_bigint() -> None:
    if engine.dialect.name != "postgresql":
        return

    bigint_columns = {
        "users": {"id", "telegram_id"},
        "locations": {"user_id", "approved_by"},
        "user_achievements": {"user_id"},
        "support_tickets": {"user_id", "closed_by"},
        "support_messages": {"sender_id"},
        "faq_entries": {"created_by"},
    }

    with engine.begin() as conn:
        existing_rows = conn.execute(
            text(
                """
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                """
            )
        ).mappings()

        existing_types = {
            (row["table_name"], row["column_name"]): row["data_type"] for row in existing_rows
        }

        columns_to_upgrade = []
        for table_name, columns in bigint_columns.items():
            for column_name in columns:
                current_type = existing_types.get((table_name, column_name))
                if current_type == "integer":
                    columns_to_upgrade.append((table_name, column_name))

        if not columns_to_upgrade:
            return

        constraints = conn.execute(
            text(
                """
                SELECT
                    con.conname AS name,
                    con.conrelid::regclass::text AS table_name,
                    pg_get_constraintdef(con.oid) AS definition
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                WHERE con.contype = 'f'
                  AND nsp.nspname = current_schema()
                """
            )
        ).mappings().all()

        constraints_to_recreate = []
        upgrade_targets = set(columns_to_upgrade)

        for con in constraints:
            table_name = con["table_name"].split(".")[-1].strip('"')
            cols = conn.execute(
                text(
                    """
                    SELECT a.attname AS column_name
                    FROM pg_constraint c
                    JOIN unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
                    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
                    WHERE c.conname = :conname
                      AND c.conrelid::regclass::text = :table_name
                    ORDER BY k.ord
                    """
                ),
                {"conname": con["name"], "table_name": con["table_name"]},
            ).mappings().all()

            if any((table_name, c["column_name"]) in upgrade_targets for c in cols):
                constraints_to_recreate.append(con)

        for con in constraints_to_recreate:
            table_name = con["table_name"].split(".")[-1].strip('"')
            conn.execute(text(f'ALTER TABLE "{table_name}" DROP CONSTRAINT "{con["name"]}"'))

        for table_name, column_name in columns_to_upgrade:
            conn.execute(
                text(
                    f'ALTER TABLE "{table_name}" ALTER COLUMN "{column_name}" TYPE BIGINT '
                    f'USING "{column_name}"::bigint'
                )
            )

        for con in constraints_to_recreate:
            table_name = con["table_name"].split(".")[-1].strip('"')
            conn.execute(
                text(
                    f'ALTER TABLE "{table_name}" ADD CONSTRAINT "{con["name"]}" {con["definition"]}'
                )
            )

        logger.info(
            "Migrated integer ID columns to BIGINT in PostgreSQL",
            extra={"columns": columns_to_upgrade},
        )


def _ensure_support_columns() -> None:
    table_columns = {
        "support_tickets": {
            "awaiting_subject": 'BOOLEAN NOT NULL DEFAULT TRUE',
            "unread_for_moderator": 'BOOLEAN NOT NULL DEFAULT TRUE',
            "unread_for_user": 'BOOLEAN NOT NULL DEFAULT FALSE',
        },
        "support_messages": {
            "message_type": "VARCHAR NOT NULL DEFAULT 'text'",
            "file_id": "VARCHAR",
            "file_name": "VARCHAR",
            "mime_type": "VARCHAR",
        },
        "support_sessions": {
            "mode": "VARCHAR NOT NULL DEFAULT 'idle'",
        },
    }

    with engine.begin() as conn:
        for table_name, columns in table_columns.items():
            existing = {col["name"] for col in inspect(conn).get_columns(table_name)}
            for column_name, column_def in columns.items():
                if column_name in existing:
                    continue
                conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_def}'))



def init_db():
    from bot.models.user import User  # noqa: F401
    from bot.models.location import Location  # noqa: F401
    from bot.models.photo import Photo  # noqa: F401
    from bot.models.tag import Tag  # noqa: F401
    from bot.models.location_tag import LocationTag  # noqa: F401
    from bot.models.achievement import Achievement  # noqa: F401
    from bot.models.season import Season  # noqa: F401
    from bot.models.user_achievement import UserAchievement  # noqa: F401
    from bot.models.faq_entry import FaqEntry  # noqa: F401
    from bot.models.support_ticket import SupportTicket, SupportMessage  # noqa: F401
    from bot.models.support_session import SupportSession  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_postgres_ids_to_bigint()
    _ensure_support_columns()
