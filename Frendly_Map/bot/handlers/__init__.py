from .start import start_handler
from .profile import profile_handler, profile_menu_handler, profile_callback_handler
from .add_location import add_location_handler
from .moderation import pending_handler, moderation_callback_handler, moderation_detail_handler
from .moderation_menu import (
    moderation_menu_handler,
    moderation_menu_callback,
    moderation_locations_handler,
    points_handler,
    delete_location_handler,
    moderation_delete_back_handler,
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
    faq_edit_start_handler,
    faq_edit_pick_handler,
    faq_edit_question_handler,
    faq_edit_answer_handler,
)
from .menu import main_menu_callback_handler


def get_all_handlers():
    return [
        start_handler,
        profile_handler,
        profile_menu_handler,
        profile_callback_handler,
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
        moderation_detail_handler,
        moderation_menu_handler,
        moderation_menu_callback,
        moderation_locations_handler,
        points_handler,
        delete_location_handler,
        moderation_delete_back_handler,
        faq_handler,
        faq_add_handler,
        faq_callback_handler,
        faq_delete_handler,
        faq_delete_confirm_handler,
        faq_edit_start_handler,
        faq_edit_pick_handler,
        faq_edit_question_handler,
        faq_edit_answer_handler,
        main_menu_callback_handler,
    ]
