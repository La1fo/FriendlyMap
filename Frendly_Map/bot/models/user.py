# bot/models/user.py
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from bot.models.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)  # Telegram ID
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    email_verified = Column(Boolean, default=False)

    pts = Column(Integer, default=0)
    points = Column(Integer, default=0)


    approved_locations = Column(Integer, default=0)
    rejected_locations = Column(Integer, default=0)
    moderation_locations = Column(Integer, default=0)
    achievements_count = Column(Integer, default=0)

    show_name_on_map = Column(Boolean, default=True)
    notify_points = Column(Boolean, default=True)
    language = Column(String, default="ru")
    theme = Column(String, default="auto")

    user_achievements = relationship(
        "UserAchievement", back_populates="user", cascade="all, delete-orphan"
    )
