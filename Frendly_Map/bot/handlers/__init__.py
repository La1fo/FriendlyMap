from .start import start_handler
from .profile import profile_handler, profile_menu_handler
from .add_location import add_location_handler
from .moderation import pending_handler, moderation_callback_handler
from .map import map_command_handler, map_menu_handler
from .leaderboard import leaderboard_handler, leaderboard_menu_handler
from .achievements import achievements_handler, achievements_menu_handler
from .moderation_panel import moderation_panel_handler
from .faq import faq_handler
from .support import support_handler
def get_all_handlers():
    return [
        start_handler,
        profile_handler,
        profile_menu_handler,
        add_location_handler,
        map_command_handler,
        map_menu_handler,
        leaderboard_handler,
        leaderboard_menu_handler,
        achievements_handler,
        achievements_menu_handler,
        faq_handler,
        support_handler,
        moderation_panel_handler,
        pending_handler,
        moderation_callback_handler,
    ]
