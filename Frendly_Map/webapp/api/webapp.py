import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from webapp.database import get_db_context
from shared.models.webapp_pick import WebAppPick
from shared.webapp_auth import validate_telegram_init_data
from webapp.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class PickerConfirmRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    init_data: str
    chat_id: int | None = None


@router.post('/picker/confirm')
def confirm_picker_point(payload: PickerConfirmRequest):
    try:
        user_payload = validate_telegram_init_data(payload.init_data, settings.BOT_TOKEN)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    logger.info("Stored webapp picker confirm", extra={"user_id": user_id, "chat_id": chat_id, "flow": "add_location", "latitude": payload.latitude, "longitude": payload.longitude})
    return {"ok": True}
