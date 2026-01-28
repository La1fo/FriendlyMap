"""Lightweight migration helper to sync DB schema with models."""

from sqlalchemy import inspect, text

from bot.database import engine, init_db


def add_column_if_missing(table: str, column: str, ddl: str) -> None:
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns(table)}
    if column in columns:
        return
    with engine.begin() as conn:
        conn.execute(text(ddl))


def main() -> None:
    init_db()

    add_column_if_missing(
        "users",
        "role",
        "ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'user'",
    )
    add_column_if_missing(
        "locations",
        "is_deleted",
        "ALTER TABLE locations ADD COLUMN is_deleted BOOLEAN DEFAULT 0",
    )
    add_column_if_missing(
        "locations",
        "deleted_at",
        "ALTER TABLE locations ADD COLUMN deleted_at TIMESTAMP NULL",
    )
    add_column_if_missing(
        "locations",
        "deleted_by",
        "ALTER TABLE locations ADD COLUMN deleted_by INTEGER NULL",
    )
    add_column_if_missing(
        "locations",
        "deleted_reason",
        "ALTER TABLE locations ADD COLUMN deleted_reason TEXT NULL",
    )

    print("✅ Migration complete.")


if __name__ == "__main__":
    main()
