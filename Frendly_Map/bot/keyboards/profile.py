# bot/keyboards/profile.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_profile_keyboard():
    keyboard = [
        [InlineKeyboardButton("⚙️ НАСТРОЙКИ", callback_data="profile_settings")],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(keyboard)
