# bot/utils/users.py
from sqlalchemy.orm import Session
from bot.models.user import User

def get_or_create_user(db: Session, telegram_user) -> User:
    """
    Получаем пользователя по Telegram ID или создаём нового
    """
    user = db.query(User).filter(User.id == telegram_user.id).first()
    if not user:
        user = User(
            id=telegram_user.id,
            username=telegram_user.username,
            full_name=telegram_user.full_name
        )
        db.add(user)
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
