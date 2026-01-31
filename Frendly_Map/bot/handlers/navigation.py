from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from bot.handlers.start import build_main_menu


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Главное меню:", reply_markup=build_main_menu(update.effective_user)
    )


main_menu_callback_handler = CallbackQueryHandler(main_menu_callback, pattern=r"^main_menu$")
