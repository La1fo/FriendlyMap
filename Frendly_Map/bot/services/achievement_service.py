# bot/services/achievement_service.py
from sqlalchemy.orm import Session
from bot.models.achievement import Achievement
from bot.models.user_achievement import UserAchievement

class AchievementService:

    @staticmethod
    def grant_achievement(db: Session, user_id: int, achievement_id: int):
        ua = db.query(UserAchievement).filter(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement_id
        ).first()
        if ua:
            return ua  # Уже есть
        ua = UserAchievement(user_id=user_id, achievement_id=achievement_id)
        db.add(ua)
        db.commit()
        db.refresh(ua)
        return ua

    @staticmethod
    def get_user_achievements(db: Session, user_id: int):
        return db.query(UserAchievement).filter(UserAchievement.user_id == user_id).all()
