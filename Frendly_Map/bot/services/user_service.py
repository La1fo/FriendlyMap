# bot/services/user_service.py
from sqlalchemy.orm import Session
from bot.models.user import User
from bot.utils.auth import hash_password, verify_password

class UserService:

    @staticmethod
    def get_or_create_user(db: Session, telegram_id: int, username=None, first_name=None, last_name=None) -> User:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    @staticmethod
    def get_user_by_email(db: Session, email: str):
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def create_user_with_email(db: Session, email: str, password: str):
        if UserService.get_user_by_email(db, email):
            raise ValueError("Email уже используется")
        user = User(
            email=email,
            password_hash=hash_password(password),
            email_verified=False
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def verify_user_password(user: User, password: str) -> bool:
        return verify_password(password, user.password_hash)
