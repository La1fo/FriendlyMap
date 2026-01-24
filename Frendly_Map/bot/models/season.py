# bot/models/season.py
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.sql import func
from .base import Base

class Season(Base):
    __tablename__ = "seasons"
    id = Column(Integer, primary_key=True)
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True))
