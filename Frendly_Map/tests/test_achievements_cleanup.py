import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

from bot.handlers import achievements as achievements_handler_mod
from bot.services.achievements_manager import AchievementsManager, DEFINITIONS
from shared.db import create_db_engine, create_session_factory, init_schema
from shared.models.achievement import Achievement
from shared.models.user import User
from shared.models.user_achievement import UserAchievement


def _setup_db(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'achievements_cleanup.db'}")
    SessionLocal = create_session_factory(engine)
    init_schema(engine)
    return SessionLocal


def test_ensure_definitions_removes_legacy_and_cleans_user_links(tmp_path):
    SessionLocal = _setup_db(tmp_path)
    manager = AchievementsManager()
    with SessionLocal() as db:
        db.add(User(id=111, telegram_id=111, username="u111", points=0, total_gp=0))
        legacy = Achievement(
            code="legacy_old_achievement",
            name="Legacy",
            description="old",
            icon="❌",
            type="standard",
            is_seasonal=False,
            points_reward=1,
            pts_reward=0,
            conditions='{"target": 1}',
        )
        db.add(legacy)
        db.flush()
        db.add(UserAchievement(user_id=111, achievement_id=legacy.id, season_id=None, progress=1, is_completed=True))
        db.commit()

        manager.ensure_definitions(db)

        all_codes = {item.code for item in db.query(Achievement).all()}
        expected_codes = {item.code for item in DEFINITIONS}
        assert all_codes == expected_codes
        assert db.query(UserAchievement).filter(UserAchievement.achievement_id == legacy.id).count() == 0


def test_achievements_menu_after_sync_does_not_show_legacy(monkeypatch, tmp_path):
    SessionLocal = _setup_db(tmp_path)
    with SessionLocal() as db:
        db.add(User(id=1, telegram_id=1, username="u1", points=0, total_gp=0))
        db.add(
            Achievement(
                code="legacy_visible",
                name="Legacy Visible",
                description="should disappear",
                icon="🧪",
                type="standard",
                is_seasonal=False,
                points_reward=1,
                pts_reward=0,
                conditions='{"target": 1}',
            )
        )
        db.commit()

    @contextmanager
    def fake_db_context():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    captured = {}

    async def fake_send_section_banner(update, context, section, caption, **kwargs):
        captured["caption"] = caption
        return SimpleNamespace(message_id=1)

    monkeypatch.setattr(achievements_handler_mod, "get_db_context", fake_db_context)
    monkeypatch.setattr(achievements_handler_mod, "send_section_banner", fake_send_section_banner)

    update = SimpleNamespace(effective_user=SimpleNamespace(id=1), callback_query=None)
    context = SimpleNamespace()
    asyncio.run(achievements_handler_mod.achievements(update, context))

    assert "Legacy Visible" not in captured["caption"]
    assert "approved" not in captured["caption"].lower()
