from sqlalchemy import func
from sqlalchemy.orm import Session

from bot.models.support_session import SupportSession
from bot.models.support_ticket import SupportTicket
from bot.utils.common import is_admin


def has_unread_moderation_tickets(db: Session) -> bool:
    return (
        db.query(func.count(SupportTicket.id))
        .filter(SupportTicket.status == "open", SupportTicket.unread_for_moderator.is_(True))
        .scalar()
        > 0
    )


def get_main_menu_unread_flag(db: Session, user_id: int) -> bool:
    if not is_admin(user_id):
        return False
    return has_unread_moderation_tickets(db)


def get_active_ticket_id(db: Session, user_id: int, scope: str) -> int | None:
    session = (
        db.query(SupportSession)
        .filter(SupportSession.user_id == user_id, SupportSession.scope == scope)
        .first()
    )
    if not session:
        return None
    return session.active_ticket_id


def set_active_ticket_id(db: Session, user_id: int, scope: str, ticket_id: int | None) -> None:
    session = (
        db.query(SupportSession)
        .filter(SupportSession.user_id == user_id, SupportSession.scope == scope)
        .first()
    )
    if not session:
        session = SupportSession(user_id=user_id, scope=scope)
        db.add(session)
    session.active_ticket_id = ticket_id
    db.commit()
