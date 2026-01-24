from .start import start_handler
from .profile import profile_handler
from .add_location import add_location_handler
from .moderation import pending_handler, moderation_callback_handler
def get_all_handlers():
    return [
        start_handler,
        profile_handler,
        add_location_handler,
        moderation_callback_handler,
    ]
