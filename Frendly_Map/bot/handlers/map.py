from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters

from bot.utils.webapp import get_map_web_app_info, webapp_url_diagnostics


def _build_map_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🗺️ Открыть карту", web_app=get_map_web_app_info())]])


async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        chat = update.callback_query.message
    else:
        chat = update.message


    ok, message = webapp_url_diagnostics()
    if not ok:
        await chat.reply_text(f"⚠️ {message}")

    await chat.reply_text(
        "Открываю карту Friendly Map!", reply_markup=_build_map_keyboard()
    )


map_command_handler = CommandHandler("map", map_command)
map_menu_handler = MessageHandler(filters.Regex("^(🗺 Карта|map)$"), map_command)
map_callback_handler = CallbackQueryHandler(map_command, pattern="^map$")
