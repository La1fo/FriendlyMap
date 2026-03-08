from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from bot.models.base import Base


class SupportSession(Base):
    __tablename__ = "support_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    scope = Column(String, nullable=False, index=True)  # user | moderator
    active_ticket_id = Column(Integer, ForeignKey("support_tickets.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
