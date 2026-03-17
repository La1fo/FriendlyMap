from sqlalchemy.orm import Session

from bot.models.user import User
from shared.rank import get_rank_progress


class GPService:
    @staticmethod
    def add_gp(db: Session, user_id: int, delta: int) -> dict[str, int | str] | None:
        user = db.get(User, user_id)
        if not user:
            return None

        user.total_gp = max(int(user.total_gp or 0) + int(delta), 0)
        # compatibility mirror for legacy paths
        user.pts = user.total_gp
        db.commit()
        db.refresh(user)
        return get_rank_progress(user.total_gp)

    @staticmethod
    def get_rank_progress(total_gp: int) -> dict[str, int | str]:
        return get_rank_progress(total_gp)
