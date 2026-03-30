# bot/utils/users.py
from sqlalchemy.orm import Session
from bot.models.user import User


def _sync_telegram_profile(user: User, telegram_user) -> bool:
    changed = False
    fresh_username = telegram_user.username or None
    fresh_first_name = telegram_user.first_name or None
    fresh_last_name = telegram_user.last_name or None

    if user.username != fresh_username:
        user.username = fresh_username
        changed = True
    if user.first_name != fresh_first_name:
        user.first_name = fresh_first_name
        changed = True
    if user.last_name != fresh_last_name:
        user.last_name = fresh_last_name
        changed = True
    if user.telegram_id != telegram_user.id:
        user.telegram_id = telegram_user.id
        changed = True
    return changed


def get_or_create_user(db: Session, telegram_user) -> User:
    """
    Получаем пользователя по Telegram ID или создаём нового
    """
    user = db.query(User).filter(User.telegram_id == telegram_user.id).first()
    if not user:
        user = User(
            id=telegram_user.id,
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    if _sync_telegram_profile(user, telegram_user):
        db.commit()
        db.refresh(user)
    return user

def update_user_settings(db: Session, user_id: int, **kwargs):
    """
    Обновляем настройки пользователя.
    Пример: update_user_settings(db, user_id, language="en", theme="dark")
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    for key, value in kwargs.items():
        if hasattr(user, key):
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user
