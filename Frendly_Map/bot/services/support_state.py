from sqlalchemy import func
from sqlalchemy.orm import Session

from bot.models.support_session import SupportSession
from bot.models.support_ticket import SUPPORT_ACTIVE_STATUSES, SupportTicket
from bot.utils.common import is_admin


def has_unread_moderation_tickets(db: Session) -> bool:
    return (
        db.query(func.count(SupportTicket.id))
        .filter(SupportTicket.status.in_(SUPPORT_ACTIVE_STATUSES), SupportTicket.unread_for_moderator.is_(True))
        .scalar()
        > 0
    )


def get_main_menu_unread_flag(db: Session, user_id: int) -> bool:
    if not is_admin(user_id):
        return False
    return has_unread_moderation_tickets(db)


def _get_or_create_session(db: Session, user_id: int, scope: str) -> SupportSession:
    session = (
        db.query(SupportSession)
        .filter(SupportSession.user_id == user_id, SupportSession.scope == scope)
        .first()
    )
    if not session:
        session = SupportSession(user_id=user_id, scope=scope, mode="idle")
        db.add(session)
        db.flush()
    return session


def get_active_ticket_id(db: Session, user_id: int, scope: str) -> int | None:
    session = (
        db.query(SupportSession)
        .filter(SupportSession.user_id == user_id, SupportSession.scope == scope)
        .first()
    )
    if not session:
        return None
    return session.active_ticket_id


def get_active_open_ticket_id(db: Session, user_id: int, scope: str) -> int | None:
    active_ticket_id = get_active_ticket_id(db, user_id, scope)
    if active_ticket_id is not None:
        active_ticket = (
            db.query(SupportTicket.id)
            .filter(SupportTicket.id == active_ticket_id, SupportTicket.status.in_(SUPPORT_ACTIVE_STATUSES))
            .first()
        )
        if active_ticket:
            return active_ticket_id

    if scope != "user":
        return None

    fallback = (
        db.query(SupportTicket.id)
        .filter(SupportTicket.user_id == user_id, SupportTicket.status.in_(SUPPORT_ACTIVE_STATUSES))
        .order_by(SupportTicket.created_at.desc())
        .first()
    )
    resolved_id = fallback[0] if fallback else None
    if resolved_id != active_ticket_id:
        set_active_ticket_id(db, user_id, scope, resolved_id)
    return resolved_id


def set_active_ticket_id(db: Session, user_id: int, scope: str, ticket_id: int | None) -> None:
    session = _get_or_create_session(db, user_id, scope)
    session.active_ticket_id = ticket_id
    if ticket_id is None and session.mode != "idle":
        session.mode = "idle"
    db.commit()


def get_session_mode(db: Session, user_id: int, scope: str) -> str:
    session = (
        db.query(SupportSession)
        .filter(SupportSession.user_id == user_id, SupportSession.scope == scope)
        .first()
    )
    if not session:
        return "idle"
    return session.mode or "idle"


def set_session_mode(db: Session, user_id: int, scope: str, mode: str) -> None:
    session = _get_or_create_session(db, user_id, scope)
    session.mode = mode
    db.commit()
