from telegram import ReplyKeyboardRemove, Update
from telegram.ext import CommandHandler, ContextTypes

from bot.database import get_db_context
from bot.keyboards.main_menu import get_main_menu
from bot.services.support_state import get_main_menu_unread_flag
from bot.utils.users import get_or_create_user

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Создаем/находим пользователя
    with get_db_context() as db:
        get_or_create_user(db, user)

    with get_db_context() as db:
        unread = get_main_menu_unread_flag(db, user.id)
    menu_message = await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n"
        "Я Friendly Map Bot — помогу тебе отмечать места и открывать карту.\n"
        "Выбери действие в меню ниже:",
        reply_markup=get_main_menu(user.id, unread_moderation=unread)
    )
    temp = await update.message.reply_text("\u2060", reply_markup=ReplyKeyboardRemove())
    try:
        await temp.delete()
    except Exception:
        pass
    context.user_data["main_menu_message_id"] = menu_message.message_id

start_handler = CommandHandler("start", start)
