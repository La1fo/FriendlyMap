# bot/services/season_service.py
from sqlalchemy.orm import Session
from bot.models.season import Season
from bot.models.user import User

class SeasonService:

    @staticmethod
    def get_current_season(db: Session):
        return Season.get_active_season(db)

    @staticmethod
    def reset_seasonal_pts(db: Session):
        db.query(User).update({User.seasonal_pts: 0})
        db.commit()
