from types import SimpleNamespace

from bot.utils.users import get_or_create_user
from shared.db import create_db_engine, create_session_factory, init_schema
from shared.models import User


def test_username_changed_removed_and_restored(tmp_path):
    db_path = tmp_path / "users.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    SessionLocal = create_session_factory(engine)
    init_schema(engine)

    tg_v1 = SimpleNamespace(id=101, username="old_name", first_name="A", last_name="B")
    tg_v2 = SimpleNamespace(id=101, username="new_name", first_name="A", last_name="B")
    tg_v3 = SimpleNamespace(id=101, username=None, first_name="A", last_name="B")
    tg_v4 = SimpleNamespace(id=101, username="restored_name", first_name="A", last_name="B")

    with SessionLocal() as db:
        user = get_or_create_user(db, tg_v1)
        assert user.telegram_id == 101
        assert user.username == "old_name"

        user = get_or_create_user(db, tg_v2)
        assert user.telegram_id == 101
        assert user.username == "new_name"

        user = get_or_create_user(db, tg_v3)
        assert user.telegram_id == 101
        assert user.username is None

        user = get_or_create_user(db, tg_v4)
        assert user.telegram_id == 101
        assert user.username == "restored_name"

        users = db.query(User).filter(User.telegram_id == 101).all()
        assert len(users) == 1
