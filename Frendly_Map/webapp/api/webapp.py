import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from bot.database import get_db_context
from bot.models.webapp_pick import WebAppPick
from webapp.config import settings

router = APIRouter()


class PickerConfirmRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    init_data: str
    chat_id: int | None = None


def _validate_telegram_init_data(init_data: str) -> dict:
    if not init_data:
        raise HTTPException(status_code=400, detail="init_data is required")

    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    provided_hash = data.pop("hash", None)
    if not provided_hash:
        raise HTTPException(status_code=400, detail="Missing hash in init_data")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, provided_hash):
        raise HTTPException(status_code=403, detail="Invalid Telegram init_data")

    user_raw = data.get("user")
    if not user_raw:
        raise HTTPException(status_code=400, detail="Missing user in init_data")

    try:
        return json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid user payload") from exc


@router.post('/picker/confirm')
def confirm_picker_point(payload: PickerConfirmRequest):
    user_payload = _validate_telegram_init_data(payload.init_data)
    user_id = int(user_payload["id"])
    chat_id = int(payload.chat_id) if payload.chat_id is not None else user_id

    with get_db_context() as db:
        db.query(WebAppPick).filter(
            WebAppPick.user_id == user_id,
            WebAppPick.chat_id == chat_id,
            WebAppPick.flow == "add_location",
            WebAppPick.processed.is_(False),
        ).delete()
        db.add(
            WebAppPick(
                user_id=user_id,
                chat_id=chat_id,
                flow="add_location",
                latitude=payload.latitude,
                longitude=payload.longitude,
                processed=False,
            )
        )
        db.commit()

    return {"ok": True}
