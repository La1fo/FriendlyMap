import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

from bot.handlers import achievements as achievements_mod
from shared.db import create_db_engine, create_session_factory, init_schema
from shared.models.achievement import Achievement
from shared.models.season import Season
from shared.models.user import User


def _setup_db(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'achievements_pagination.db'}")
    SessionLocal = create_session_factory(engine)
    init_schema(engine)
    return SessionLocal


def _insert_achievements(db, kind: str, count: int):
    for idx in range(1, count + 1):
        db.add(
            Achievement(
                code=f"{kind}_{idx}",
                name=f"{kind.upper()} #{idx}",
                description=f"desc {idx}",
                icon="🏆",
                type=kind,
                is_seasonal=(kind == "ranked"),
                points_reward=1,
                pts_reward=0,
                conditions='{"target": 1}',
            )
        )


def _make_update(callback_data: str | None):
    if callback_data is None:
        return SimpleNamespace(effective_user=SimpleNamespace(id=1), callback_query=None)

    async def fake_answer():
        return None

    return SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        callback_query=SimpleNamespace(data=callback_data, answer=fake_answer),
    )


def _run_and_capture(monkeypatch, SessionLocal, callback_data: str | None):
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
        captured["reply_markup"] = kwargs.get("reply_markup")
        return SimpleNamespace(message_id=1)

    monkeypatch.setattr(achievements_mod, "get_db_context", fake_db_context)
    monkeypatch.setattr(achievements_mod, "send_section_banner", fake_send_section_banner)
    monkeypatch.setattr(achievements_mod.AchievementsManager, "ensure_definitions", lambda *_a, **_k: None)
    monkeypatch.setattr(achievements_mod.AchievementsManager, "get_current_season", lambda *_a, **_k: SimpleNamespace(id=1, key="2026-Q2"))

    update = _make_update(callback_data)
    context = SimpleNamespace()
    asyncio.run(achievements_mod.achievements(update, context))
    return captured


def test_standard_and_ranked_pagination_and_labels(monkeypatch, tmp_path):
    SessionLocal = _setup_db(tmp_path)
    with SessionLocal() as db:
        db.add(User(id=1, telegram_id=1, username="u1", points=0, total_gp=0))
        db.add(Season(id=1, key="2026-Q2"))
        _insert_achievements(db, "standard", 7)
        _insert_achievements(db, "ranked", 6)
        db.commit()

    page1 = _run_and_capture(monkeypatch, SessionLocal, "achievements_standard_page_1")
    assert "STANDARD #1" in page1["caption"]
    assert "STANDARD #5" in page1["caption"]
    assert "STANDARD #6" not in page1["caption"]
    assert "Временные" not in page1["caption"]
    tab_labels = [btn.text for btn in page1["reply_markup"].inline_keyboard[0]]
    assert any("Сезонные" in label for label in tab_labels)
    assert all("Временные" not in label for label in tab_labels)
    assert page1["reply_markup"].inline_keyboard[1][1].text == "1/2"

    page2 = _run_and_capture(monkeypatch, SessionLocal, "achievements_standard_page_2")
    assert "STANDARD #6" in page2["caption"]
    assert "STANDARD #1" not in page2["caption"]
    assert page2["reply_markup"].inline_keyboard[1][1].text == "2/2"
    assert page2["reply_markup"].inline_keyboard[1][2].text == "·"

    ranked_page1 = _run_and_capture(monkeypatch, SessionLocal, "achievements_ranked_page_1")
    assert "⏱️ Сезонные достижения" in ranked_page1["caption"]
    assert "RANKED #1" in ranked_page1["caption"]
    assert "RANKED #5" in ranked_page1["caption"]
    assert "RANKED #6" not in ranked_page1["caption"]

    cb_data = ranked_page1["reply_markup"].inline_keyboard[1][2].callback_data
    assert cb_data == "achievements_ranked_page_2"


def test_less_than_page_size_and_page_clamp(monkeypatch, tmp_path):
    SessionLocal = _setup_db(tmp_path)
    with SessionLocal() as db:
        db.add(User(id=1, telegram_id=1, username="u1", points=0, total_gp=0))
        db.add(Season(id=1, key="2026-Q2"))
        _insert_achievements(db, "standard", 3)
        db.commit()

    captured = _run_and_capture(monkeypatch, SessionLocal, "achievements_standard_page_99")
    assert "STANDARD #1" in captured["caption"]
    assert "STANDARD #3" in captured["caption"]
    assert "STANDARD #4" not in captured["caption"]
    assert len(captured["reply_markup"].inline_keyboard) == 2  # tabs + back, no pagination row
