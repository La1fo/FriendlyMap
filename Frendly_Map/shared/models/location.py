from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from .base import Base


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String)
    status = Column(String, default="pending")
    approved_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    moderation_comment = Column(Text, nullable=True)
    moderated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
