from pathlib import Path
import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

from bot.handlers import add_location


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
