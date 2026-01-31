from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from bot.models.location import Location
from bot.models.moderation_log import ModerationLog
from bot.models.user import User


class ModerationService:
    @staticmethod
    def approve_location(db: Session, moderator_id: int, location: Location) -> None:
        location.status = "approved"
        location.approved_by = moderator_id
        location.moderated_at = datetime.now(timezone.utc)
        ModerationService._log(db, moderator_id, "approve_location", location_id=location.id)

    @staticmethod
    def reject_location(db: Session, moderator_id: int, location: Location, reason: str) -> None:
        location.status = "rejected"
        location.moderation_comment = reason
        location.approved_by = moderator_id
        location.moderated_at = datetime.now(timezone.utc)
        ModerationService._log(db, moderator_id, "reject_location", location_id=location.id, reason=reason)

    @staticmethod
    def delete_location(db: Session, moderator_id: int, location: Location, reason: str) -> None:
        location.is_deleted = True
        location.status = "deleted"
        location.deleted_at = datetime.now(timezone.utc)
        location.deleted_by = moderator_id
        location.deleted_reason = reason
        ModerationService._log(db, moderator_id, "delete_location", location_id=location.id, reason=reason)

    @staticmethod
    def adjust_user_points(
        db: Session,
        moderator_id: int,
        user: User,
        delta_pts: int,
        delta_points: int,
        reason: str,
    ) -> None:
        user.pts += delta_pts
        user.points += delta_points
        ModerationService._log(
            db,
            moderator_id,
            "adjust_points",
            target_user_id=user.id,
            delta_pts=delta_pts,
            delta_points=delta_points,
            reason=reason,
        )

    @staticmethod
    def _log(
        db: Session,
        moderator_id: int,
        action: str,
        location_id: Optional[int] = None,
        target_user_id: Optional[int] = None,
        delta_pts: int = 0,
        delta_points: int = 0,
        reason: Optional[str] = None,
    ) -> None:
        log = ModerationLog(
            moderator_id=moderator_id,
            action=action,
            location_id=location_id,
            target_user_id=target_user_id,
            delta_pts=delta_pts,
            delta_points=delta_points,
            reason=reason,
        )
        db.add(log)
