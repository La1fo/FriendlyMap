import logging
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from webapp.database import get_db_context
from shared.models.location import Location
from shared.models.webapp_pick import WebAppPick
from shared.webapp_auth import validate_telegram_init_data
from webapp.config import is_admin_id, settings

router = APIRouter()
logger = logging.getLogger(__name__)


class PickerConfirmRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    init_data: str
    chat_id: int | None = None
    tag_ids: list[int] = Field(default_factory=list)

    @field_validator("tag_ids")
    @classmethod
    def validate_tag_ids(cls, value: list[int]) -> list[int]:
        normalized = sorted({int(x) for x in value if int(x) > 0})
        if len(normalized) > 5:
            raise ValueError("Можно выбрать не более 5 тегов")
        return normalized


class DeleteLocationRequest(BaseModel):
    location_id: int = Field(..., gt=0)
    init_data: str
    confirm: bool = False


@router.post('/picker/confirm')
def confirm_picker_point(payload: PickerConfirmRequest):
    logger.info(
        "Received webapp picker confirm request",
        extra={"chat_id": payload.chat_id, "tag_ids_count": len(payload.tag_ids)},
    )
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
                tag_ids_json=json.dumps(payload.tag_ids, ensure_ascii=False),
                processed=False,
            )
        )
        db.commit()

    logger.info(
        "Stored webapp picker confirm",
        extra={
            "user_id": user_id,
            "chat_id": chat_id,
            "flow": "add_location",
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "tag_ids_count": len(payload.tag_ids),
        },
    )
    return {"ok": True}


@router.post("/moderation/delete-location")
def moderation_delete_location(payload: DeleteLocationRequest):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Требуется подтверждение удаления")
    try:
        user_payload = validate_telegram_init_data(payload.init_data, settings.BOT_TOKEN)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    moderator_id = int(user_payload["id"])
    if not is_admin_id(moderator_id):
        raise HTTPException(status_code=403, detail="Только для модераторов")

    with get_db_context() as db:
        loc = db.get(Location, payload.location_id)
        if not loc or loc.status == "deleted":
            raise HTTPException(status_code=404, detail="Локация не найдена")
        loc.status = "deleted"
        loc.approved_by = moderator_id
        loc.moderated_at = datetime.utcnow()
        db.commit()

    logger.info(
        "Delete via map confirmed",
        extra={"moderator_id": moderator_id, "location_id": payload.location_id},
    )
    return {"ok": True}
