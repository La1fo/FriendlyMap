from pathlib import Path

from bot.services.gp_service import GPService
from shared.db import create_db_engine, create_session_factory, init_schema
from shared.models import User


def test_add_gp_rollover_from_99_to_102(tmp_path: Path):
    db_path = tmp_path / "gp.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    SessionLocal = create_session_factory(engine)
    init_schema(engine)

    with SessionLocal() as db:
        db.add(User(id=10, telegram_id=10, username="u", total_gp=99, pts=99, points=0))
        db.commit()

    with SessionLocal() as db:
        payload = GPService.add_gp(db, 10, 3)

    assert payload is not None
    assert payload["total_gp"] == 102
    assert payload["rank_level"] == 2
    assert payload["gp_in_rank"] == 2
