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
        db.add(User(id=2, telegram_id=2, username="top_master", total_gp=2000, points=0))
        for idx in range(3, 13):
            db.add(User(id=idx, telegram_id=idx, username=f"u{idx}", total_gp=1413 - idx, points=0))
        db.add(User(id=13, telegram_id=13, username="not_top10", total_gp=1300, points=0))
        db.commit()

    with engine.begin() as conn:
        row = conn.execute(text("SELECT total_gp, rank_level, gp_in_rank, rank_name FROM site_leaderboard WHERE user_id=1")).first()
        assert row[0] == 135
        assert row[1] == 2
        assert row[2] == 35
        assert row[3] == "🟢 Исследователь 2"

        top_master_row = conn.execute(
            text("SELECT rank_level, gp_in_rank, rank_name, position FROM site_leaderboard WHERE user_id=2")
        ).first()
        assert top_master_row[0] == 11
        assert top_master_row[1] == 400
        assert top_master_row[2] == "⭐ Мастер-картограф"
        assert top_master_row[3] <= 10

        not_top10_row = conn.execute(
            text("SELECT rank_level, gp_in_rank, rank_name FROM site_public_users WHERE user_id=13")
        ).first()
        assert not_top10_row[0] == 10
        assert not_top10_row[1] == 400
        assert not_top10_row[2] == "🟣 Картограф"

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


def test_rank_view_sql_uses_postgres_compatible_least():
    source = Path("shared/migrations.py").read_text(encoding="utf-8")

    assert "MIN(u.total_gp - 900, 400)" not in source
    assert "LEAST(GREATEST(u.total_gp - 900, 0), 400)" in source
