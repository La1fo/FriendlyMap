# bot/keyboards/main_menu.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.config import settings

def get_main_menu(user_id: int):
    buttons = [
        [InlineKeyboardButton("🗺️ КАРТА", web_app={"url": settings.WEB_APP_URL + "/map"})],
        [InlineKeyboardButton("🏪 МАГАЗИН", web_app={"url": settings.WEB_APP_URL + "/shop"})],
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
