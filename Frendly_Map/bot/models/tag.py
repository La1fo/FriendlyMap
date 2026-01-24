# bot/models/tag.py
from sqlalchemy import Column, Integer, String
from .base import Base

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, default="general")
