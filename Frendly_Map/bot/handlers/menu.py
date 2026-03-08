from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from bot.keyboards.main_menu import get_main_menu
from bot.database import get_db_context
from bot.services.support_state import get_main_menu_unread_flag


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    message = query.message
    with get_db_context() as db:
        unread = get_main_menu_unread_flag(db, update.effective_user.id)
    menu = get_main_menu(update.effective_user.id, unread_moderation=unread)
    await query.edit_message_text("Главное меню:", reply_markup=menu)
    context.user_data["main_menu_message_id"] = message.message_id


main_menu_callback_handler = CallbackQueryHandler(show_main_menu, pattern="^menu_back$")
