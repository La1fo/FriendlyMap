import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bot.handlers.faq import _render_faq_text
from bot.models.base import Base
from bot.models.faq_entry import FaqEntry
from bot.models.support_session import SupportSession
from bot.models.support_ticket import SupportTicket
from bot.services.support_state import get_active_ticket_id, has_unread_moderation_tickets, set_active_ticket_id


class SupportFaqTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)

    def test_support_session_persistence_primitives(self):
        db = self.Session()
        ticket = SupportTicket(user_id=1, status="open", unread_for_moderator=True)
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        set_active_ticket_id(db, 42, "moderator", ticket.id)
        active = get_active_ticket_id(db, 42, "moderator")
        self.assertEqual(active, ticket.id)

        self.assertTrue(has_unread_moderation_tickets(db))
        ticket.unread_for_moderator = False
        db.commit()
        self.assertFalse(has_unread_moderation_tickets(db))

        set_active_ticket_id(db, 42, "moderator", None)
        self.assertIsNone(get_active_ticket_id(db, 42, "moderator"))
        db.close()

    def test_faq_render_escapes_html(self):
        entries = [
            FaqEntry(question="<b>q?</b>", answer="<script>alert(1)</script>"),
        ]
        text = _render_faq_text(entries)
        self.assertIn("&lt;b&gt;q?&lt;/b&gt;", text)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", text)


if __name__ == "__main__":
    unittest.main()
