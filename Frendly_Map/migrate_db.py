"""Run minimal schema migrations (role column, new tables)."""

from sqlalchemy import inspect, text

from bot.database import engine, init_db


def add_role_column() -> None:
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("users")]
    if "role" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'"))


def main() -> None:
    init_db()
    add_role_column()
    print("✅ Migrations applied.")


if __name__ == "__main__":
    main()
