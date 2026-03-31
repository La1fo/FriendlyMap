import hashlib
import hmac
import json
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from shared.models.location import Location
from shared.models.webapp_pick import WebAppPick
from webapp.database import get_db_context, init_db
from webapp.main import app


def _build_init_data(user_payload: dict, bot_token: str) -> str:
    data = {
        "auth_date": "1700000000",
        "query_id": "AAEAAQ",
        "user": json.dumps(user_payload, separators=(",", ":"), ensure_ascii=False),
    }
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def test_picker_confirm_endpoint(monkeypatch):
    bot_token = "123:ABC"
    monkeypatch.setattr("webapp.api.webapp.settings.BOT_TOKEN", bot_token)

    init_data = _build_init_data({"id": 5001, "first_name": "T"}, bot_token)

    init_db()
    client = TestClient(app)
    resp = client.post(
        "/api/webapp/picker/confirm",
        json={
            "latitude": 55.75,
            "longitude": 37.61,
            "init_data": init_data,
            "chat_id": 5001,
            "tag_ids": [1, 2, 2, 3],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    with get_db_context() as db:
        item = (
            db.query(WebAppPick)
            .filter(WebAppPick.user_id == 5001, WebAppPick.chat_id == 5001, WebAppPick.flow == "add_location")
            .order_by(WebAppPick.id.desc())
            .first()
        )
        assert item is not None
        assert float(item.latitude) == 55.75
        assert json.loads(item.tag_ids_json or "[]") == [1, 2, 3]


def test_delete_via_map_requires_admin(monkeypatch):
    bot_token = "123:ABC"
    monkeypatch.setattr("webapp.api.webapp.settings.BOT_TOKEN", bot_token)
    monkeypatch.setattr("webapp.api.webapp.settings.ADMIN_IDS", "9001")
    monkeypatch.setattr("webapp.config.settings.ADMIN_IDS", "9001")

    init_data_non_admin = _build_init_data({"id": 5002, "first_name": "U"}, bot_token)
    init_data_admin = _build_init_data({"id": 9001, "first_name": "A"}, bot_token)
    location_id = 1999

    init_db()
    with get_db_context() as db:
        existing = db.get(Location, location_id)
        if existing:
            db.delete(existing)
            db.flush()
        db.add(Location(id=location_id, user_id=5002, name="L", latitude=1.0, longitude=2.0, status="approved"))
        db.commit()

    client = TestClient(app)
    denied = client.post(
        "/api/webapp/moderation/delete-location",
        json={"location_id": location_id, "init_data": init_data_non_admin, "confirm": True},
    )
    assert denied.status_code == 403

    ok = client.post(
        "/api/webapp/moderation/delete-location",
        json={"location_id": location_id, "init_data": init_data_admin, "confirm": True},
    )
    assert ok.status_code == 200
    assert ok.json()["ok"] is True
