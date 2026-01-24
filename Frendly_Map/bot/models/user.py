# bot/models/user.py
from sqlalchemy import Column, Integer, String, Boolean
from bot.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)  # внутренний ID
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)

    pts = Column(Integer, default=0)
    points = Column(Integer, default=0)


    approved_locations = Column(Integer, default=0)
    rejected_locations = Column(Integer, default=0)
    moderation_locations = Column(Integer, default=0)
    achievements = Column(Integer, default=0)

    show_name_on_map = Column(Boolean, default=True)
    notify_points = Column(Boolean, default=True)
    language = Column(String, default="ru")
    theme = Column(String, default="auto")
