import hashlib
import hmac
import json
from urllib.parse import urlencode

from fastapi.testclient import TestClient

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
