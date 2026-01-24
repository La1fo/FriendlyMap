# bot/models/photo.py
from sqlalchemy import Column, Integer, String, ForeignKey
from .base import Base

class Photo(Base):
    __tablename__ = "photos"
    id = Column(Integer, primary_key=True)
    location_id = Column(Integer, ForeignKey("locations.id"))
    file_id = Column(String, nullable=False)
    order_index = Column(Integer, default=0)
