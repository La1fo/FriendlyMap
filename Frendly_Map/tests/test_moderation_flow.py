import asyncio
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from bot.handlers import moderation, moderation_menu
from shared.db import create_db_engine, create_session_factory, init_schema
from shared.models.location import Location
from shared.models.photo import Photo
from shared.models.user import User


def _setup_db(tmp_path):
    db_path = tmp_path / "mod.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    SessionLocal = create_session_factory(engine)
    init_schema(engine)
    return SessionLocal


def test_location_detail_shows_actions_without_auto_photo(monkeypatch, tmp_path):
    SessionLocal = _setup_db(tmp_path)
    with SessionLocal() as db:
        db.add(User(id=1, telegram_id=1, username="author", points=0, total_gp=0))
        db.add(Location(id=10, user_id=1, name="Loc", latitude=1.0, longitude=2.0, status="pending"))
        db.add(Photo(location_id=10, file_id="photo-file", order_index=0))
        db.commit()

    @contextmanager
    def fake_db_context():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    edited = {}
    sent_photos = []

    async def fake_edit_message_text(text, reply_markup=None, parse_mode=None):
        edited["text"] = text
        edited["markup"] = reply_markup

    async def fake_answer():
        return None

    async def fake_send_photo(**kwargs):
        sent_photos.append(kwargs)

    monkeypatch.setattr(moderation, "get_db_context", fake_db_context)
    monkeypatch.setattr(moderation, "is_admin", lambda _uid: True)

    query = SimpleNamespace(
        data="loc_detail_10",
        answer=fake_answer,
        edit_message_text=fake_edit_message_text,
        message=SimpleNamespace(chat_id=99),
    )
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=999))
    context = SimpleNamespace(bot=SimpleNamespace(send_photo=fake_send_photo))

    asyncio.run(moderation.show_location_detail(update, context))

    assert "📍 <b>Loc</b>" in edited["text"]
    buttons = edited["markup"].inline_keyboard
    assert buttons[0][0].text == "✔️ Одобрить"
    assert buttons[0][1].text == "❌ Отклонить"
    assert buttons[1][0].text == "🗺️ Карта"
    assert "moderation=1" in buttons[1][0].web_app.url
    assert "focus_location_id=10" in buttons[1][0].web_app.url
    assert sent_photos == []


def test_standard_rewards_granted_only_on_approve(monkeypatch, tmp_path):
    SessionLocal = _setup_db(tmp_path)
    with SessionLocal() as db:
        db.add(User(id=1, telegram_id=1, username="u1", points=0, total_gp=0, moderation_locations=1))
        db.add(User(id=2, telegram_id=2, username="u2", points=0, total_gp=0, moderation_locations=1))
        db.add(Location(id=11, user_id=1, name="Approve me", latitude=1.0, longitude=2.0, status="pending"))
        db.add(Location(id=12, user_id=2, name="Reject me", latitude=3.0, longitude=4.0, status="pending"))
        db.commit()

    @contextmanager
    def fake_db_context():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    async def fake_answer():
        return None

    async def fake_edit_message_text(*args, **kwargs):
        return None

    async def fake_send_message(*args, **kwargs):
        return None

    async def fake_moderation_menu(update, context):
        return None

    monkeypatch.setattr(moderation, "get_db_context", fake_db_context)
    monkeypatch.setattr(moderation, "is_admin", lambda _uid: True)
    monkeypatch.setattr(moderation, "moderation_menu", fake_moderation_menu)
    monkeypatch.setattr(moderation.AchievementsManager, "apply_event", lambda *_a, **_k: [])

    approve_query = SimpleNamespace(data="approve_11", answer=fake_answer, message=SimpleNamespace(message_id=1), edit_message_text=fake_edit_message_text)
    update = SimpleNamespace(callback_query=approve_query, effective_user=SimpleNamespace(id=900))
    context = SimpleNamespace(user_data={}, bot=SimpleNamespace(send_message=fake_send_message))
    asyncio.run(moderation.handle_callback(update, context))

    reject_query = SimpleNamespace(data="reject_12", answer=fake_answer, message=SimpleNamespace(message_id=2), edit_message_text=fake_edit_message_text)
    update_reject = SimpleNamespace(callback_query=reject_query, effective_user=SimpleNamespace(id=900))
    asyncio.run(moderation.handle_callback(update_reject, context))

    with SessionLocal() as db:
        u1 = db.get(User, 1)
        u2 = db.get(User, 2)
        loc1 = db.get(Location, 11)
        loc2 = db.get(Location, 12)

        assert loc1.status == "approved"
        assert u1.points == moderation.APPROVE_BASE_POINTS
        assert u1.total_gp == moderation.APPROVE_BASE_GP

        assert loc2.status == "rejected"
        assert u2.total_gp == 0


def test_extra_gp_capped_and_extra_coins_unlimited(monkeypatch, tmp_path):
    SessionLocal = _setup_db(tmp_path)
    with SessionLocal() as db:
        db.add(User(id=5, telegram_id=5, username="u5", points=0, total_gp=0))
        db.commit()

    @contextmanager
    def fake_db_context():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    async def fake_reply_text(_text):
        return None

    monkeypatch.setattr(moderation, "get_db_context", fake_db_context)
    async def fake_moderation_menu(*_a, **_k):
        return None

    monkeypatch.setattr(moderation, "moderation_menu", fake_moderation_menu)

    # cap check
    context = SimpleNamespace(user_data={"extra_reward_location_id": 100, "extra_reward_user_id": 5, "extra_reward_type": "gp"})
    update = SimpleNamespace(message=SimpleNamespace(text="61", reply_text=fake_reply_text), effective_user=SimpleNamespace(id=10))
    state = asyncio.run(moderation.extra_reward_amount(update, context))
    assert state == moderation.EXTRA_REWARD_AMOUNT

    # unlimited coins
    context = SimpleNamespace(user_data={"extra_reward_location_id": 100, "extra_reward_user_id": 5, "extra_reward_type": "coins"})
    update = SimpleNamespace(message=SimpleNamespace(text="500", reply_text=fake_reply_text), effective_user=SimpleNamespace(id=10))
    asyncio.run(moderation.extra_reward_amount(update, context))

    with SessionLocal() as db:
        user = db.get(User, 5)
        assert user.points == 500


def test_delete_menu_contains_map_delete_mode_button(monkeypatch, tmp_path):
    edited = {}

    async def fake_edit_message_text(text, reply_markup):
        edited["text"] = text
        edited["markup"] = reply_markup

    async def fake_answer():
        return None

    monkeypatch.setattr(moderation_menu, "_ensure_admin", lambda _u: True)

    query = SimpleNamespace(answer=fake_answer, message=SimpleNamespace(), edit_message_text=fake_edit_message_text)
    update = SimpleNamespace(effective_user=SimpleNamespace(id=42), callback_query=query)
    context = SimpleNamespace(user_data={})

    asyncio.run(moderation_menu.delete_location_start(update, context))

    first_row_button = edited["markup"].inline_keyboard[0][0]
    assert first_row_button.text == "🗺 Удалить через карту"
    assert "mod_delete=1" in first_row_button.web_app.url
    assert len(edited["markup"].inline_keyboard) == 2


def test_moderation_locations_handler_opens_review_map_from_menu(monkeypatch, tmp_path):
    edited = {}

    async def fake_edit_message_text(text, reply_markup):
        edited["text"] = text
        edited["markup"] = reply_markup

    async def fake_answer():
        return None

    monkeypatch.setattr(moderation_menu, "_ensure_admin", lambda _u: True)

    query = SimpleNamespace(answer=fake_answer, edit_message_text=fake_edit_message_text)
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=9001))
    context = SimpleNamespace()

    asyncio.run(moderation_menu.moderation_locations(update, context))
    assert "Открой карту модерации" in edited["text"]
    map_button = edited["markup"].inline_keyboard[0][0]
    assert map_button.text == "🗺️ Открыть карту модерации"
    assert "moderation=1" in map_button.web_app.url


def test_review_mode_marker_styles_pending_red_approved_blue():
    script_path = Path(__file__).resolve().parents[1] / "webapp" / "static" / "script.js"
    content = script_path.read_text(encoding="utf-8")
    assert 'loc.status === "pending"' in content
    assert "#dc2626" in content
    assert 'loc.status === "approved"' in content
    assert "#3b82f6" in content
    assert 'loc.status === "pending"' in content
    assert "applyModerationAction(\"approve\")" in content
    assert "applyModerationAction(\"reject\")" in content
