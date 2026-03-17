import hashlib
import hmac
import json
from urllib.parse import parse_qsl


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict:
    if not init_data:
        raise ValueError("init_data is required")
    if not bot_token:
        raise ValueError("BOT_TOKEN is not configured")

    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    provided_hash = data.pop("hash", None)
    if not provided_hash:
        raise ValueError("Missing hash in init_data")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, provided_hash):
        raise PermissionError("Invalid Telegram init_data")

    user_raw = data.get("user")
    if not user_raw:
        raise ValueError("Missing user in init_data")

    try:
        return json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid user payload") from exc
