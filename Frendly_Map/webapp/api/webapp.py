import logging
import json
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import urlopen

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from webapp.database import get_db_context
from shared.models.location import Location
from shared.models.user import User
from shared.models.webapp_pick import WebAppPick
from shared.models.moderation_followup import ModerationFollowup
from shared.webapp_auth import validate_telegram_init_data
from webapp.config import is_admin_id, settings
from bot.services.gp_service import GPService
from bot.services.achievements_manager import AchievementsManager

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


class ModerationReviewActionRequest(BaseModel):
    location_id: int = Field(..., gt=0)
    action: str = Field(..., pattern="^(approve|reject)$")
    init_data: str


def _notify_bonus_followup(moderator_id: int, followup_id: int, location_name: str) -> None:
    if not settings.BOT_TOKEN:
        return
    keyboard = {
        "inline_keyboard": [
            [{"text": "💰 Доп монеты", "callback_data": f"web_bonus_coins_{followup_id}"}],
            [{"text": "🎯 Доп GP (до 60)", "callback_data": f"web_bonus_gp_{followup_id}"}],
            [{"text": "⏭ Пропустить", "callback_data": f"web_bonus_skip_{followup_id}"}],
        ]
    }
    payload = {
        "chat_id": moderator_id,
        "text": f"Локация <b>{location_name}</b> одобрена ✅\n\nВыдать дополнительную награду?",
        "parse_mode": "HTML",
        "reply_markup": json.dumps(keyboard, ensure_ascii=False),
    }
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage?{urlencode(payload)}"
    with urlopen(url, timeout=8):
        pass


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
    logger.info("Delete target location selected", extra={"location_id": payload.location_id, "confirm": payload.confirm})
    if not payload.confirm:
        logger.warning("Delete via map rejected: confirmation flag missing", extra={"location_id": payload.location_id})
        raise HTTPException(status_code=400, detail="Требуется подтверждение удаления")
    try:
        user_payload = validate_telegram_init_data(payload.init_data, settings.BOT_TOKEN)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    moderator_id = int(user_payload["id"])
    if not is_admin_id(moderator_id):
        logger.warning("Delete via map rejected: unauthorized user", extra={"user_id": moderator_id, "location_id": payload.location_id})
        raise HTTPException(status_code=403, detail="Только для модераторов")

    with get_db_context() as db:
        loc = db.get(Location, payload.location_id)
        if not loc or loc.status == "deleted":
            logger.warning("Delete via map failed: location not found", extra={"moderator_id": moderator_id, "location_id": payload.location_id})
            raise HTTPException(status_code=404, detail="Локация не найдена")
        if loc.status != "approved":
            logger.warning(
                "Delete via map rejected: location is not approved",
                extra={"moderator_id": moderator_id, "location_id": payload.location_id, "status": loc.status},
            )
            raise HTTPException(status_code=400, detail="Удаление доступно только для одобренных локаций")
        logger.info("Delete confirmed", extra={"moderator_id": moderator_id, "location_id": payload.location_id})
        loc.status = "deleted"
        loc.approved_by = moderator_id
        loc.moderated_at = datetime.utcnow()
        db.commit()

    logger.info(
        "Delete completed",
        extra={"moderator_id": moderator_id, "location_id": payload.location_id},
    )
    return {"ok": True}


@router.post("/moderation/review-action")
def moderation_review_action(payload: ModerationReviewActionRequest):
    logger.info("Moderation review action clicked", extra={"location_id": payload.location_id, "action": payload.action})
    try:
        user_payload = validate_telegram_init_data(payload.init_data, settings.BOT_TOKEN)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    moderator_id = int(user_payload["id"])
    if not is_admin_id(moderator_id):
        raise HTTPException(status_code=403, detail="Только для модераторов")

    achievements = AchievementsManager()
    with get_db_context() as db:
        loc = db.get(Location, payload.location_id)
        if not loc:
            raise HTTPException(status_code=404, detail="Локация не найдена")
        if loc.status != "pending":
            raise HTTPException(status_code=400, detail="Действие доступно только для pending-локаций")

        owner = db.get(User, loc.user_id)
        if payload.action == "approve":
            loc.status = "approved"
            loc.approved_by = moderator_id
            loc.moderated_at = datetime.utcnow()
            if owner:
                owner.points += 15
                owner.approved_locations += 1
                owner.moderation_locations = max(owner.moderation_locations - 1, 0)
                GPService.add_gp(db, owner.id, 10)
                achievements.apply_event(
                    db,
                    owner.id,
                    "coins_earned",
                    15,
                    event_key=f"webapp_approval_coins:{loc.id}",
                )
                achievements.apply_event(
                    db,
                    owner.id,
                    "location_approved",
                    1,
                    event_key=f"webapp_approval:{loc.id}",
                )

            followup = db.query(ModerationFollowup).filter(ModerationFollowup.location_id == loc.id).first()
            if followup is None:
                followup = ModerationFollowup(
                    moderator_id=moderator_id,
                    location_id=loc.id,
                    owner_id=loc.user_id,
                    status="pending",
                )
                db.add(followup)
                db.flush()
                logger.info("Post-approval bonus follow-up scheduled", extra={"location_id": loc.id, "followup_id": followup.id})
                try:
                    _notify_bonus_followup(moderator_id, followup.id, loc.name)
                    logger.info("Post-approval bonus menu shown in bot", extra={"followup_id": followup.id, "moderator_id": moderator_id})
                except Exception as exc:
                    logger.warning("Unable to notify bonus follow-up", extra={"followup_id": followup.id, "error": str(exc)})
            else:
                logger.info("Duplicate follow-up prevented", extra={"location_id": loc.id, "followup_id": followup.id})
        else:
            loc.status = "rejected"
            loc.approved_by = moderator_id
            loc.moderated_at = datetime.utcnow()
            if owner:
                owner.points = max(owner.points - 5, 0)
                owner.rejected_locations += 1
                owner.moderation_locations = max(owner.moderation_locations - 1, 0)
                achievements.apply_event(
                    db,
                    owner.id,
                    "location_rejected",
                    1,
                    event_key=f"webapp_reject:{loc.id}",
                )
        db.commit()

    logger.info("Moderation review action completed", extra={"location_id": payload.location_id, "action": payload.action})
    return {"ok": True, "status": "approved" if payload.action == "approve" else "rejected"}
