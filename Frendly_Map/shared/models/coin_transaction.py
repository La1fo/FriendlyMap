from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from .base import Base


class CoinTransaction(Base):
    __tablename__ = "coin_transactions"
    __table_args__ = (UniqueConstraint("event_key", name="uq_coin_transactions_event_key"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=True, index=True)
    amount = Column(Integer, nullable=False)
    reason = Column(String(64), nullable=False, default="unknown")
    event_key = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
