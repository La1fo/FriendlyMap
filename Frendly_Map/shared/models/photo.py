from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from .base import Base


class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True)
    location_id = Column(Integer, ForeignKey("locations.id"))
    file_id = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
