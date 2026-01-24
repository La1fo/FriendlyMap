# bot/models/achievement.py
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    icon = Column(String(10), nullable=False)
    points_reward = Column(Integer, default=0)
    pts_reward = Column(Integer, default=0)
    is_seasonal = Column(Boolean, default=False)
    conditions = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_achievements = relationship("UserAchievement", back_populates="achievement", cascade="all, delete-orphan")
