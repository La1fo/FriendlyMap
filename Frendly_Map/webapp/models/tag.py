# webapp/madels/tag.py
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship
from .base import Base

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    category = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    location_tags = relationship("LocationTag", back_populates="tag", cascade="all, delete-orphan")
