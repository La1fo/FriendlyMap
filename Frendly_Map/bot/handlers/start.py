from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes

from bot.database import get_db_session
from bot.utils.users import get_or_create_user

MAIN_MENU = [
    ["🗺 Карта", "➕ Добавить"],
    ["👤 Профиль", "🏆 Рейтинг"]
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Создаем/находим пользователя
    with next(get_db_session()) as db:
        get_or_create_user(db, user)

    keyboard = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)

    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n"
        "Я Friendly Map Bot — помогу тебе отмечать места и открывать карту!",
        reply_markup=keyboard
    )

start_handler = CommandHandler("start", start)
