from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes

from bot.database import get_db_context
from bot.utils.common import is_moderator
from bot.utils.users import get_or_create_user

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Создаем/находим пользователя
    with get_db_context() as db:
        get_or_create_user(db, user)
        is_mod = is_moderator(db, user.id)

    menu = [
        ["🗺 Карта", "➕ Добавить"],
        ["👤 Профиль", "🏆 Лидеры"],
        ["🏆 Достижения"],
    ]
    if is_mod:
        menu.append(["🛡 Модерация"])

    keyboard = ReplyKeyboardMarkup(menu, resize_keyboard=True)

    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n"
        "Я Friendly Map Bot — помогу тебе отмечать места и открывать карту!",
        reply_markup=keyboard
    )

start_handler = CommandHandler("start", start)
