import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

from bot.handlers import achievements as achievements_handler_mod
from shared.db import create_db_engine, create_session_factory, init_schema
from shared.models.achievement import Achievement
from shared.models.season import Season
from shared.models.user import User


def _setup_db(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'achievements_html.db'}")
    SessionLocal = create_session_factory(engine)
    init_schema(engine)
    return SessionLocal


def test_achievements_menu_escapes_html_like_text(monkeypatch, tmp_path):
    SessionLocal = _setup_db(tmp_path)
    with SessionLocal() as db:
        db.add(User(id=1, telegram_id=1, username="u1", points=0, total_gp=0))
        db.add(Season(id=1, key="2026-Q2"))
        db.add(
            Achievement(
                code="unsafe",
                name='Broken <b> title',
                description='desc with <tag> & symbols',
                icon="🏆",
                type="standard",
                is_seasonal=False,
                points_reward=10,
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
    monkeypatch.setattr(achievements_handler_mod.AchievementsManager, "ensure_definitions", lambda *_a, **_k: None)
    monkeypatch.setattr(achievements_handler_mod.AchievementsManager, "get_current_season", lambda *_a, **_k: SimpleNamespace(id=1, key="2026-Q2"))

    update = SimpleNamespace(effective_user=SimpleNamespace(id=1), callback_query=None)
    context = SimpleNamespace()

    asyncio.run(achievements_handler_mod.achievements(update, context))

    assert "&lt;b&gt;" in captured["caption"]
    assert "&lt;tag&gt;" in captured["caption"]
    assert "Broken <b> title" not in captured["caption"]
