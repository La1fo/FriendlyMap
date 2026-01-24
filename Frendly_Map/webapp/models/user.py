# webapp/madels/user.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from .base import Base
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=True)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    locations = relationship("Location", back_populates="user")
