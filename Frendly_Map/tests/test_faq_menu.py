import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

from bot.handlers import faq as faq_mod
from shared.db import create_db_engine, create_session_factory, init_schema
from bot.models.faq_entry import FaqEntry


def _setup_db(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'faq.db'}")
    SessionLocal = create_session_factory(engine)
    init_schema(engine)
    return SessionLocal


def test_faq_screen_contains_site_hint_and_existing_entries(monkeypatch, tmp_path):
    SessionLocal = _setup_db(tmp_path)
    with SessionLocal() as db:
        db.add(FaqEntry(question="Как добавить локацию?", answer="Через кнопку в меню."))
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
        captured["section"] = section
        captured["caption"] = caption
        captured["reply_markup"] = kwargs.get("reply_markup")
        return SimpleNamespace(message_id=1)

    monkeypatch.setattr(faq_mod, "get_db_context", fake_db_context)
    monkeypatch.setattr(faq_mod, "get_section_banner", lambda _s: {"title": "FAQ", "description": "Частые вопросы"})
    monkeypatch.setattr(faq_mod, "send_section_banner", fake_send_section_banner)

    update = SimpleNamespace(callback_query=None, effective_user=SimpleNamespace(id=100))
    context = SimpleNamespace()

    asyncio.run(faq_mod.show_faq(update, context))

    assert captured["section"] == "faq"
    assert "ответы на вопросы" in captured["caption"].lower()
    assert "чат с поддержкой" in captured["caption"].lower()
    assert "Как добавить локацию?" in captured["caption"]
    assert "Через кнопку в меню." in captured["caption"]

    keyboard = captured["reply_markup"].inline_keyboard
    assert keyboard[0][0].text == "🌐 Открыть сайт"
    assert keyboard[0][0].url == "https://map.friendlymap.ru"
    assert keyboard[1][0].text == "◀️ Назад"
    assert keyboard[1][0].callback_data == "menu_back"


def test_faq_screen_empty_entries_still_mentions_site_and_support(monkeypatch, tmp_path):
    SessionLocal = _setup_db(tmp_path)

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

    monkeypatch.setattr(faq_mod, "get_db_context", fake_db_context)
    monkeypatch.setattr(faq_mod, "get_section_banner", lambda _s: {"title": "FAQ", "description": "Частые вопросы"})
    monkeypatch.setattr(faq_mod, "send_section_banner", fake_send_section_banner)

    update = SimpleNamespace(callback_query=None, effective_user=SimpleNamespace(id=100))
    context = SimpleNamespace()

    asyncio.run(faq_mod.show_faq(update, context))

    text = captured["caption"].lower()
    assert "ответы на вопросы" in text
    assert "чат с поддержкой" in text
    assert "пока нет вопросов" in text

    keyboard = captured["reply_markup"].inline_keyboard
    assert keyboard[0][0].url == "https://map.friendlymap.ru"


def test_faq_handlers_are_unchanged_entrypoints():
    assert faq_mod.faq_handler is not None
    assert faq_mod.faq_callback_handler is not None
    assert faq_mod.faq_menu_handler is not None
