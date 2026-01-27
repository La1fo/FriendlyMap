from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from .base import Base


class ModerationLog(Base):
    __tablename__ = "moderation_logs"

    id = Column(Integer, primary_key=True)
    moderator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    delta_points = Column(Integer, default=0)
    delta_pts = Column(Integer, default=0)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
