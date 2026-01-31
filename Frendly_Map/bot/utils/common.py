from bot.config import settings
from bot.models.user import User


def is_admin(user_id: int) -> bool:
    return str(user_id) in settings.ADMIN_IDS.split(",")


def is_moderator(db, user_id: int) -> bool:
    if is_admin(user_id):
        return True
    user = db.get(User, user_id)
    if not user:
        return False
    return user.role in {"moderator", "admin"}
