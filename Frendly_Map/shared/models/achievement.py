from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import Base


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    icon = Column(String(10), nullable=False)
    points_reward = Column(Integer, default=0)
    pts_reward = Column(Integer, default=0)
    type = Column(String(20), default="standard")
    is_seasonal = Column(Boolean, default=False)
    conditions = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_achievements = relationship("UserAchievement", back_populates="achievement", cascade="all, delete-orphan")
