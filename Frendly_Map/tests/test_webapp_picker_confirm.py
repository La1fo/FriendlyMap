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


def test_delete_via_map_requires_confirmation_and_approved_status(monkeypatch):
    bot_token = "123:ABC"
    monkeypatch.setattr("webapp.api.webapp.settings.BOT_TOKEN", bot_token)
    monkeypatch.setattr("webapp.api.webapp.settings.ADMIN_IDS", "9001")
    monkeypatch.setattr("webapp.config.settings.ADMIN_IDS", "9001")

    init_data_admin = _build_init_data({"id": 9001, "first_name": "A"}, bot_token)

    init_db()
    with get_db_context() as db:
        for loc_id in (2991, 2992):
            existing = db.get(Location, loc_id)
            if existing:
                db.delete(existing)
        db.flush()
        db.add(Location(id=2991, user_id=9001, name="Approved L", latitude=1.0, longitude=2.0, status="approved"))
        db.add(Location(id=2992, user_id=9001, name="Pending L", latitude=2.0, longitude=3.0, status="pending"))
        db.commit()

    client = TestClient(app)
    no_confirm = client.post(
        "/api/webapp/moderation/delete-location",
        json={"location_id": 2991, "init_data": init_data_admin, "confirm": False},
    )
    assert no_confirm.status_code == 400

    pending_rejected = client.post(
        "/api/webapp/moderation/delete-location",
        json={"location_id": 2992, "init_data": init_data_admin, "confirm": True},
    )
    assert pending_rejected.status_code == 400


def test_moderation_review_action_approve_reject_and_acl(monkeypatch):
    bot_token = "123:ABC"
    monkeypatch.setattr("webapp.api.webapp.settings.BOT_TOKEN", bot_token)
    monkeypatch.setattr("webapp.api.webapp.settings.ADMIN_IDS", "9001")
    monkeypatch.setattr("webapp.config.settings.ADMIN_IDS", "9001")

    init_data_admin = _build_init_data({"id": 9001, "first_name": "A"}, bot_token)
    init_data_user = _build_init_data({"id": 5002, "first_name": "U"}, bot_token)

    init_db()
    with get_db_context() as db:
        for loc_id in (3771, 3772):
            existing = db.get(Location, loc_id)
            if existing:
                db.delete(existing)
        db.flush()
        db.add(Location(id=3771, user_id=5002, name="P1", latitude=1.0, longitude=2.0, status="pending"))
        db.add(Location(id=3772, user_id=5002, name="P2", latitude=1.1, longitude=2.1, status="pending"))
        db.commit()

    client = TestClient(app)
    denied = client.post(
        "/api/webapp/moderation/review-action",
        json={"location_id": 3771, "action": "approve", "init_data": init_data_user},
    )
    assert denied.status_code == 403

    approved = client.post(
        "/api/webapp/moderation/review-action",
        json={"location_id": 3771, "action": "approve", "init_data": init_data_admin},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    rejected = client.post(
        "/api/webapp/moderation/review-action",
        json={"location_id": 3772, "action": "reject", "init_data": init_data_admin},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
