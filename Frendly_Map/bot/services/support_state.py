from sqlalchemy import func
from sqlalchemy.orm import Session

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
