import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bot.handlers.faq import _render_faq_text
from bot.models.base import Base
from bot.models.faq_entry import FaqEntry
from bot.models.support_ticket import SupportTicket
from bot.services.location_service import LocationService
from bot.services.support_state import (
    get_active_open_ticket_id,
    get_active_ticket_id,
    get_session_mode,
    has_unread_moderation_tickets,
    set_active_ticket_id,
    set_session_mode,
)


class SupportFaqTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)



    def test_location_service_ensure_tags_is_idempotent(self):
        db = self.Session()
        catalog = {"Еда": ["кафе", "бар"], "Отдых": ["парк"]}
        LocationService.ensure_tags(db, catalog)
        LocationService.ensure_tags(db, catalog)

        from bot.models.tag import Tag
        tags = db.query(Tag).all()
        self.assertEqual(len(tags), 3)
        db.close()

    def test_add_tags_by_ids_avoids_duplicates(self):
        db = self.Session()
        from bot.models.location import Location
        from bot.models.tag import Tag
        from bot.models.location_tag import LocationTag

        loc = Location(user_id=1, name="test", latitude=1.0, longitude=2.0, status="pending")
        t1 = Tag(name="кафе", category="Еда")
        t2 = Tag(name="парк", category="Отдых")
        db.add_all([loc, t1, t2])
        db.commit()
        db.refresh(loc)
        db.refresh(t1)
        db.refresh(t2)

        LocationService.add_tags_by_ids(db, loc.id, [t1.id, t2.id, t1.id])
        LocationService.add_tags_by_ids(db, loc.id, [t2.id])

        links = db.query(LocationTag).filter(LocationTag.location_id == loc.id).all()
        self.assertEqual(len(links), 2)
        db.close()

    def test_support_ticket_default_status_is_new(self):
        db = self.Session()
        ticket = SupportTicket(user_id=1)
        db.add(ticket)
        db.flush()
        self.assertEqual(ticket.status, "new")
        db.close()

    def test_get_active_open_ticket_id_repairs_stale_session(self):
        db = self.Session()
        closed_ticket = SupportTicket(user_id=1, status="closed", unread_for_moderator=False, awaiting_subject=False)
        open_ticket = SupportTicket(user_id=1, status="new", unread_for_moderator=True, awaiting_subject=False)
        db.add_all([closed_ticket, open_ticket])
        db.commit()
        db.refresh(closed_ticket)
        db.refresh(open_ticket)

        set_active_ticket_id(db, 1, "user", closed_ticket.id)
        resolved = get_active_open_ticket_id(db, 1, "user")
        self.assertEqual(resolved, open_ticket.id)
        self.assertEqual(get_active_ticket_id(db, 1, "user"), open_ticket.id)
        db.close()

    def test_support_session_persistence_primitives(self):
        db = self.Session()
        ticket = SupportTicket(user_id=1, status="new", unread_for_moderator=True)
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


    def test_support_session_mode_roundtrip(self):
        db = self.Session()
        self.assertEqual(get_session_mode(db, 99, "user"), "idle")
        set_session_mode(db, 99, "user", "reply_text")
        self.assertEqual(get_session_mode(db, 99, "user"), "reply_text")
        set_active_ticket_id(db, 99, "user", None)
        self.assertEqual(get_session_mode(db, 99, "user"), "idle")
        db.close()

    def test_main_menu_has_no_support_button(self):
        from bot.keyboards.main_menu import get_main_menu

        kb = get_main_menu(user_id=1)
        labels = [btn.text for row in kb.inline_keyboard for btn in row]
        self.assertNotIn("🆘 ПОДДЕРЖКА", labels)

    def test_faq_render_escapes_html(self):
        entries = [
            FaqEntry(question="<b>q?</b>", answer="<script>alert(1)</script>"),
        ]
        text = _render_faq_text(entries)
        self.assertIn("&lt;b&gt;q?&lt;/b&gt;", text)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", text)

if __name__ == "__main__":
    unittest.main()
