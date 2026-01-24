from bot.config import settings

def is_admin(user_id: int) -> bool:
    return str(user_id) in settings.ADMIN_IDS.split(",")
