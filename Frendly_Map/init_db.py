"""Create all database tables."""

from bot.database import init_db


def main() -> None:
    init_db()
    print("✅ Database tables created.")


if __name__ == "__main__":
    main()
