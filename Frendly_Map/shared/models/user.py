from sqlalchemy import BigInteger, Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    email_verified = Column(Boolean, default=False)

    pts = Column(Integer, default=0)
    total_gp = Column(Integer, default=0, nullable=False)
    points = Column(Integer, default=0)

    approved_locations = Column(Integer, default=0)
    rejected_locations = Column(Integer, default=0)
    moderation_locations = Column(Integer, default=0)
    achievements_count = Column(Integer, default=0)

    show_name_on_map = Column(Boolean, default=True)
    notify_points = Column(Boolean, default=True)
    language = Column(String, default="ru")
    theme = Column(String, default="auto")

    user_achievements = relationship("UserAchievement", back_populates="user", cascade="all, delete-orphan")
