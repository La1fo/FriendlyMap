from datetime import datetime, timezone
from sqlalchemy.orm import Session

from bot.models.ticket import Ticket
from bot.models.ticket_message import TicketMessage


class TicketService:
    @staticmethod
    def get_open_ticket(db: Session, user_id: int):
        return db.query(Ticket).filter(Ticket.user_id == user_id, Ticket.status == "open").first()

    @staticmethod
    def get_or_create_open_ticket(db: Session, user_id: int) -> Ticket:
        ticket = TicketService.get_open_ticket(db, user_id)
        if ticket:
            return ticket
        ticket = Ticket(user_id=user_id, status="open")
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return ticket

    @staticmethod
    def list_user_tickets(db: Session, user_id: int):
        return db.query(Ticket).filter(Ticket.user_id == user_id).order_by(Ticket.created_at.desc()).all()

    @staticmethod
    def list_open_tickets(db: Session):
        return db.query(Ticket).filter(Ticket.status == "open").order_by(Ticket.created_at.desc()).all()

    @staticmethod
    def add_message(db: Session, ticket_id: int, author_role: str, author_id: int, text: str) -> TicketMessage:
        message = TicketMessage(
            ticket_id=ticket_id,
            author_role=author_role,
            author_id=author_id,
            text=text,
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    @staticmethod
    def close_ticket(db: Session, ticket: Ticket) -> None:
        ticket.status = "closed"
        ticket.closed_at = datetime.now(timezone.utc)
        db.commit()

    @staticmethod
    def list_messages(db: Session, ticket_id: int):
        return (
            db.query(TicketMessage)
            .filter(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at.asc())
            .all()
        )
