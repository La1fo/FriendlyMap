import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest

from shared.webapp_auth import validate_telegram_init_data


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


def test_validate_init_data_success():
    bot_token = "123:ABC"
    payload = {"id": 42, "first_name": "Test"}
    init_data = _build_init_data(payload, bot_token)

    user = validate_telegram_init_data(init_data, bot_token)
    assert user["id"] == 42


def test_validate_init_data_invalid_hash():
    bot_token = "123:ABC"
    payload = {"id": 42, "first_name": "Test"}
    init_data = _build_init_data(payload, bot_token) + "tampered"

    with pytest.raises(PermissionError):
        validate_telegram_init_data(init_data, bot_token)
