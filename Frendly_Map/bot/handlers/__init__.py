from .start import start_handler
from .profile import (
    profile_handler,
    profile_menu_handler,
    profile_callback_handler,
    profile_tickets_menu_handler,
    profile_tickets_list_handler,
    profile_ticket_chat_handler,
    profile_ticket_back_handler,
    profile_ticket_close_handler,
)
from .add_location import add_location_handler
from .moderation import pending_handler, moderation_callback_handler
from .moderation_menu import (
    moderation_menu_handler,
    moderation_menu_callback,
    moderation_locations_handler,
    points_handler,
    delete_location_handler,
    tickets_handler,
    moderation_close_ticket_handler,
    moderation_ticket_back_handler,
    moderation_ticket_close_handler,
)
from .map import map_command_handler, map_menu_handler, map_callback_handler
from .leaderboard import leaderboard_handler, leaderboard_menu_handler, leaderboard_callback_handler
from .achievements import achievements_handler, achievements_menu_handler, achievements_callback_handler
from .faq import (
    faq_handler,
    faq_add_handler,
    faq_callback_handler,
    faq_delete_handler,
    faq_delete_confirm_handler,
)
from .support import (
    support_handler,
    support_callback_handler,
    support_chat_handler,
    support_close_handler,
    support_message_router,
    moderator_message_router,
)
from .menu import main_menu_callback_handler
def get_all_handlers():
    return [
        start_handler,
        profile_handler,
        profile_menu_handler,
        profile_callback_handler,
        profile_tickets_menu_handler,
        profile_tickets_list_handler,
        profile_ticket_chat_handler,
        profile_ticket_back_handler,
        profile_ticket_close_handler,
        add_location_handler,
        map_command_handler,
        map_menu_handler,
        map_callback_handler,
        leaderboard_handler,
        leaderboard_menu_handler,
        leaderboard_callback_handler,
        achievements_handler,
        achievements_menu_handler,
        achievements_callback_handler,
        pending_handler,
        moderation_callback_handler,
        moderation_menu_handler,
        moderation_menu_callback,
        moderation_locations_handler,
        points_handler,
        delete_location_handler,
        tickets_handler,
        moderation_close_ticket_handler,
        moderation_ticket_back_handler,
        moderation_ticket_close_handler,
        faq_handler,
        faq_add_handler,
        faq_callback_handler,
        faq_delete_handler,
        faq_delete_confirm_handler,
        support_handler,
        support_callback_handler,
        support_chat_handler,
        support_close_handler,
        support_message_router,
        moderator_message_router,
        main_menu_callback_handler,
    ]
