import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bot.handlers.faq import _render_faq_text
from bot.handlers.profile import _format_ticket_history, _ticket_view_keyboard
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

    def test_profile_ticket_keyboard_hides_close_for_closed_ticket(self):
        kb_open = _ticket_view_keyboard([], ticket_id=10, ticket_status="open", list_kind="active")
        kb_closed = _ticket_view_keyboard([], ticket_id=10, ticket_status="closed", list_kind="archive")

        open_labels = [btn.text for row in kb_open.inline_keyboard for btn in row]
        closed_labels = [btn.text for row in kb_closed.inline_keyboard for btn in row]

        self.assertIn("✅ Закрыть тикет", open_labels)
        self.assertNotIn("✅ Закрыть тикет", closed_labels)

    def test_profile_ticket_keyboard_contains_attachment_buttons(self):
        messages = [
            {"id": 1, "message_type": "photo", "file_id": "p1", "message": "Фото"},
            {"id": 2, "message_type": "document", "file_id": "d1", "file_name": "a.txt", "message": "Док"},
            {"id": 3, "message_type": "text", "file_id": None, "message": "Привет"},
        ]
        kb = _ticket_view_keyboard(messages, ticket_id=1, ticket_status="open", list_kind="active")
        labels = [btn.text for row in kb.inline_keyboard for btn in row]
        self.assertIn("🖼 Вложение #1", labels)
        self.assertIn("📄 Вложение #2", labels)

    def test_ticket_history_format_for_attachments(self):
        history = _format_ticket_history([
            {"sender_role": "user", "created_at": None, "message_type": "text", "message": "Привет"},
            {"sender_role": "moderator", "created_at": None, "message_type": "photo", "message": "Фото", "file_name": None},
            {"sender_role": "moderator", "created_at": None, "message_type": "document", "message": "Файл", "file_name": "doc.pdf"},
        ])
        self.assertIn("Привет", history)
        self.assertIn("[Фото] Фото", history)
        self.assertIn("[Документ (doc.pdf)] Файл", history)


if __name__ == "__main__":
    unittest.main()
