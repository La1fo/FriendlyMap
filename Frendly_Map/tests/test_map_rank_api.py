from fastapi.testclient import TestClient

from shared.models.location import Location
from shared.models.user import User
from webapp.database import get_db_context, init_db
from webapp.main import app
from tests.test_webapp_picker_confirm import _build_init_data


def test_approved_locations_include_author_rank_fields():
    init_db()
    with get_db_context() as db:
        user = db.get(User, 9001)
        if not user:
            user = User(id=9001, telegram_id=9001, username="rank_user", total_gp=102, points=0)
            db.add(user)
            db.commit()
        loc = Location(
            user_id=9001,
            name="Test place",
            description="Desc",
            latitude=55.75,
            longitude=37.61,
            address="Addr",
            status="approved",
        )
        db.add(loc)
        db.commit()

    client = TestClient(app)
    resp = client.get("/api/map/locations/approved")
    assert resp.status_code == 200
    payload = resp.json()
    found = [x for x in payload["items"] if x["name"] == "Test place"]
    assert found
    author = found[-1]["author"]
    assert set(author.keys()) == {"user_id", "total_gp", "rank_level", "gp_in_rank", "rank_name"}
    assert author["total_gp"] == 102
    assert author["rank_level"] == 2
    assert author["gp_in_rank"] == 2
    assert author["rank_name"] == "🟢 Исследователь 2"


def test_moderation_locations_require_admin(monkeypatch):
    bot_token = "123:ABC"
    monkeypatch.setattr("webapp.api.map.settings.BOT_TOKEN", bot_token)
    monkeypatch.setattr("webapp.api.map.settings.ADMIN_IDS", "9001")
    monkeypatch.setattr("webapp.config.settings.ADMIN_IDS", "9001")
    init_data_admin = _build_init_data({"id": 9001, "first_name": "A"}, bot_token)
    init_data_user = _build_init_data({"id": 9002, "first_name": "U"}, bot_token)

    init_db()
    with get_db_context() as db:
        user = db.get(User, 19002)
        if not user:
            user = User(id=19002, telegram_id=19002, username="pending_user", total_gp=0, points=0)
            db.add(user)
            db.flush()
        db.add(Location(user_id=19002, name="Pending L", latitude=1.0, longitude=2.0, status="pending"))
        db.commit()

    client = TestClient(app)
    denied = client.get("/api/map/locations/moderation", params={"init_data": init_data_user})
    assert denied.status_code == 403

    ok = client.get("/api/map/locations/moderation", params={"init_data": init_data_admin})
    assert ok.status_code == 200
    names = [item["name"] for item in ok.json()["items"]]
    assert "Pending L" in names
