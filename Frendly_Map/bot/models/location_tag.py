# bot/models/location_tag.py
from sqlalchemy import Column, Integer, ForeignKey
from .base import Base

class LocationTag(Base):
    __tablename__ = "location_tags"
    id = Column(Integer, primary_key=True)
    location_id = Column(Integer, ForeignKey("locations.id"))
    tag_id = Column(Integer, ForeignKey("tags.id"))
