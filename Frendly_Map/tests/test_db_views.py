from pathlib import Path

from sqlalchemy import text

from shared.db import create_db_engine, create_session_factory, init_schema
from shared.models import User
from shared.migrations import run_migrations


def _view_columns(conn, view_name: str) -> list[str]:
    return [row[1] for row in conn.execute(text(f"PRAGMA table_info({view_name})"))]


def test_site_views_created_with_contract(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    SessionLocal = create_session_factory(engine)
    init_schema(engine)

    with engine.begin() as conn:
        views = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='view'"))}
        assert "site_leaderboard" in views
        assert "site_public_users" in views
        assert "site_public_locations" in views
        assert "site_achievements_overview" in views
        assert "site_auth_users" in views

        assert _view_columns(conn, "site_public_users") == [
            "user_id", "username", "telegram_id", "total_gp", "rank_level", "gp_in_rank", "rank_name", "approved_locations"
        ]
        assert _view_columns(conn, "site_leaderboard") == [
            "user_id", "username", "total_gp", "rank_level", "gp_in_rank", "rank_name", "position"
        ]
        assert _view_columns(conn, "site_public_locations") == ["location_id", "user_id"]
        assert _view_columns(conn, "site_achievements_overview") == [
            "achievement_id", "code", "name", "description", "completed_count", "is_seasonal"
        ]
        assert _view_columns(conn, "site_auth_users") == [
            "user_id", "username", "telegram_id", "email", "hashed_password"
        ]

    with SessionLocal() as db:
        db.add(User(id=1, telegram_id=1, username="u1", total_gp=135, points=10, email="u@example.com", password_hash="hashed"))
        db.commit()

    with engine.begin() as conn:
        row = conn.execute(text("SELECT total_gp, rank_level, gp_in_rank, rank_name FROM site_leaderboard WHERE user_id=1")).first()
        assert row[0] == 135
        assert row[1] == 2
        assert row[2] == 35
        assert row[3] == "Ранг 2"

        auth_row = conn.execute(text("SELECT email, hashed_password FROM site_auth_users WHERE user_id=1")).first()
        assert auth_row[0] == "u@example.com"
        assert auth_row[1] == "hashed"


def test_run_migrations_recreates_views_even_on_current_schema(tmp_path: Path):
    db_path = tmp_path / "test_idempotent.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    init_schema(engine)

    with engine.begin() as conn:
        conn.execute(text("DROP VIEW site_leaderboard"))

    run_migrations(engine)

    with engine.begin() as conn:
        views = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='view'"))}
        assert "site_leaderboard" in views
