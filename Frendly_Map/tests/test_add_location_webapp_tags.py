from pathlib import Path
import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

from bot.handlers import add_location
from shared.db import create_db_engine, create_session_factory, init_schema
from shared.models.webapp_pick import WebAppPick


def test_add_location_no_longer_has_bot_tag_selection_states():
    source = Path("bot/handlers/add_location.py").read_text(encoding="utf-8")

    assert "ASK_TAG_CATEGORY" not in source
    assert "ASK_TAG_PICK" not in source
    assert "CB_TAG_TOGGLE" not in source
    assert "CB_TAG_CAT" not in source


def test_add_location_uses_webapp_tags_payload():
    source = Path("bot/handlers/add_location.py").read_text(encoding="utf-8")

    assert "tag_ids_json" in source
    assert "selected_tag_ids" in source
    assert "next_state\": ASK_PHOTO" in source


def test_confirm_renders_selected_tags_from_db(monkeypatch):
    captured: dict[str, str] = {}

    async def fake_render_flow_message(update, context, text_value, reply_markup):
        captured["text"] = text_value

    class _FakeTagQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def all(self):
            return [SimpleNamespace(name="кафе", category="Еда")]

    class _FakeDb:
        def query(self, _model):
            return _FakeTagQuery()

    @contextmanager
    def fake_db_context():
        yield _FakeDb()

    async def _answer():
        return None

    update = SimpleNamespace(callback_query=SimpleNamespace(answer=_answer), message=None)
    context = SimpleNamespace(
        user_data={
            "loc_name": "Тест",
            "loc_description": "Описание",
            "latitude": 10.0,
            "longitude": 20.0,
            "photos": ["ph1"],
            "selected_tag_ids": [1],
        }
    )

    async def _run():
        monkeypatch.setattr(add_location, "_render_flow_message", fake_render_flow_message)
        monkeypatch.setattr(add_location, "get_db_context", fake_db_context)
        await add_location.confirm(update, context)

    asyncio.run(_run())

    assert "кафе (Еда)" in captured["text"]


def test_pending_pick_advances_to_photo_step_and_marks_processed(monkeypatch, tmp_path):
    db_path = tmp_path / "handoff.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    SessionLocal = create_session_factory(engine)
    init_schema(engine)

    with SessionLocal() as db:
        db.add(
            WebAppPick(
                user_id=7001,
                chat_id=7001,
                flow="add_location",
                latitude=55.75,
                longitude=37.61,
                tag_ids_json="[3, 5, 5]",
                processed=False,
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

    shown: dict[str, bool] = {"called": False}

    async def fake_photo_step(_update, _context):
        shown["called"] = True
        return add_location.ASK_PHOTO

    fake_app = SimpleNamespace(user_data={7001: {"add_location_message_id": 1}}, bot_data={})
    fake_bot = object()

    monkeypatch.setattr(add_location, "get_db_context", fake_db_context)
    monkeypatch.setattr(add_location.LocationService, "ensure_tags", lambda db, catalog: None)
    monkeypatch.setattr(add_location, "_proceed_to_photo_step", fake_photo_step)

    add_location.add_location_handler._conversations.clear()
    advanced = asyncio.run(add_location._advance_from_pending_pick(fake_app, fake_bot, 7001, 7001))

    assert advanced is True
    assert shown["called"] is True
    assert fake_app.user_data[7001]["latitude"] == 55.75
    assert fake_app.user_data[7001]["longitude"] == 37.61
    assert fake_app.user_data[7001]["selected_tag_ids"] == [3, 5]
    assert add_location.add_location_handler._conversations[(7001, 7001)] == add_location.ASK_PHOTO

    with SessionLocal() as db:
        item = db.query(WebAppPick).first()
        assert item.processed is True


def test_selected_tag_ids_reach_save_flow(monkeypatch):
    calls: dict[str, list[int] | None] = {"tag_ids": None}

    @contextmanager
    def fake_db_context():
        yield object()

    def fake_get_or_create_user(_db, _user):
        return None

    def fake_create_location(_db, **_kwargs):
        return SimpleNamespace(id=99)

    def fake_add_tags(_db, _location_id, selected_ids):
        calls["tag_ids"] = list(selected_ids)

    def fake_add_photo(_db, _loc_id, _file_id, order_index):
        return None

    async def fake_answer():
        return None

    async def fake_delete_message(*_args, **_kwargs):
        return None

    async def fake_show_main_menu(*_args, **_kwargs):
        return None

    monkeypatch.setattr(add_location, "get_db_context", fake_db_context)
    monkeypatch.setattr(add_location, "get_or_create_user", fake_get_or_create_user)
    monkeypatch.setattr(add_location.LocationService, "create_location", fake_create_location)
    monkeypatch.setattr(add_location.LocationService, "add_tags_by_ids", fake_add_tags)
    monkeypatch.setattr(add_location.LocationService, "add_photo", fake_add_photo)
    monkeypatch.setattr(add_location.AchievementsManager, "apply_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(add_location, "_show_main_menu", fake_show_main_menu)
    monkeypatch.setattr(add_location, "_stop_geo_pick_poll", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(add_location, "_clear_pending_geo_pick", lambda *_args, **_kwargs: None)

    update = SimpleNamespace(
        callback_query=SimpleNamespace(answer=fake_answer),
        effective_user=SimpleNamespace(id=42),
        effective_chat=SimpleNamespace(id=42),
    )
    context = SimpleNamespace(
        user_data={
            "loc_name": "Point",
            "loc_description": "Desc",
            "latitude": 1.0,
            "longitude": 2.0,
            "photos": ["photo-a"],
            "selected_tag_ids": [8, 9],
            "add_location_message_id": 1,
        },
        bot=SimpleNamespace(delete_message=fake_delete_message),
    )

    result = asyncio.run(add_location.save(update, context))

    assert result == add_location.ConversationHandler.END
    assert calls["tag_ids"] == [8, 9]
