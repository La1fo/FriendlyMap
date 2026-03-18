from sqlalchemy import func
from sqlalchemy.orm import Session

from bot.config import settings
from bot.models.user import User
from shared.rank import get_rank_progress


class LeaderboardService:
    @staticmethod
    def ensure_sample_users(db: Session) -> None:
        if not settings.SEED_SAMPLE_DATA:
            return
        total = db.query(User).count()
        if total > 1:
            return

        samples = [
            User(username="Explorer", first_name="Explorer", total_gp=120, points=300),
            User(username="Mapper", first_name="Mapper", total_gp=260, points=550),
            User(username="Master", first_name="Master", total_gp=520, points=900),
        ]
        db.add_all(samples)
        db.commit()

    @staticmethod
    def get_top_users(db: Session, limit: int = 10):
        return (
            db.query(User)
            .order_by(User.total_gp.desc(), User.id.asc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_user_position(db: Session, user_id: int) -> tuple[int, int]:
        user = db.get(User, user_id)
        if not user:
            return 0, 0
        higher_or_earlier_count = (
            db.query(func.count(User.id))
            .filter(
                (User.total_gp > user.total_gp)
                | ((User.total_gp == user.total_gp) & (User.id < user.id))
            )
            .scalar()
        )
        total = db.query(func.count(User.id)).scalar()
        return higher_or_earlier_count + 1, total

    @staticmethod
    def get_rank_title(points: int, leaderboard_position: int | None = None) -> str:
        return str(get_rank_progress(points, leaderboard_position=leaderboard_position)["rank_name"])
