from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from .base import Base


class ModerationFollowup(Base):
    __tablename__ = "moderation_followups"
    __table_args__ = (UniqueConstraint("location_id", name="uq_moderation_followup_location"),)

    id = Column(Integer, primary_key=True)
    moderator_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False, index=True)
    owner_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(16), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    handled_at = Column(DateTime(timezone=True), nullable=True)
