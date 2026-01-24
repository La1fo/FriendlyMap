# webapp/madels/location_tag.py
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship
from .base import Base

class LocationTag(Base):
    __tablename__ = "location_tags"

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"))
    tag_id = Column(Integer, ForeignKey("tags.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    location = relationship("Location", back_populates="tags")
    tag = relationship("Tag", back_populates="location_tags")
