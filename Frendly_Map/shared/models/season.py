from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from .base import Base


class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True)
    key = Column(String(20), unique=True, nullable=False)
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True))
