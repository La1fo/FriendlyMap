# bot/keyboards/main_menu.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import settings
from bot.utils.webapp import build_webapp_url, get_map_web_app_info

def get_main_menu(user_id: int):
    buttons = [
        [InlineKeyboardButton("🗺️ КАРТА", web_app=get_map_web_app_info())],
        [InlineKeyboardButton("🏪 МАГАЗИН", web_app={"url": build_webapp_url("/shop")})],
        [InlineKeyboardButton("👤 ПРОФИЛЬ", callback_data="profile"),
         InlineKeyboardButton("➕ ДОБАВИТЬ ЛОКАЦИЮ", callback_data="add_location")],
        [InlineKeyboardButton("🏆 ДОСТИЖЕНИЯ", callback_data="achievements"),
         InlineKeyboardButton("📊 ТАБЛИЦА ЛИДЕРОВ", callback_data="leaderboard")],
        [InlineKeyboardButton("❓ F.A.Q.", callback_data="faq")]
    ]

    # Админ-кнопка
    if str(user_id) in settings.ADMIN_IDS.split(","):
        buttons.append([InlineKeyboardButton("⚙️ МОДЕРАЦИЯ", callback_data="moderation")])

    return InlineKeyboardMarkup(buttons)
