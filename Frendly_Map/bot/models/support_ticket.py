from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from bot.models.base import Base


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="open", nullable=False)
    subject = Column(String, nullable=True)
    awaiting_subject = Column(Boolean, default=True, nullable=False)
    unread_for_moderator = Column(Boolean, default=True, nullable=False)
    unread_for_user = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)
    closed_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    closed_reason = Column(Text, nullable=True)

    messages = relationship(
        "SupportMessage", back_populates="ticket", cascade="all, delete-orphan"
    )


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("support_tickets.id"), nullable=False)
    sender_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    sender_role = Column(String, nullable=False)
    message_type = Column(String, default="text", nullable=False)
    message = Column(Text, nullable=False)
    file_id = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    mime_type = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ticket = relationship("SupportTicket", back_populates="messages")
