from pathlib import Path

from sqlalchemy import text

from shared.db import create_db_engine, create_session_factory, init_schema
from shared.models import User


def test_site_views_created(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    SessionLocal = create_session_factory(engine)
    init_schema(engine)

    with engine.begin() as conn:
        tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='view'"))}
        assert "site_leaderboard" in tables
        assert "site_public_users" in tables
        assert "site_public_locations" in tables
        assert "site_achievements_overview" in tables

    with SessionLocal() as db:
        db.add(User(id=1, telegram_id=1, username="u1", pts=135, points=10))
        db.commit()

    with engine.begin() as conn:
        row = conn.execute(text("SELECT total_gp, gp_in_rank FROM site_leaderboard WHERE user_id=1")).first()
        assert row[0] == 135
        assert row[1] == 35
