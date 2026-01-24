from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from bot.config import settings


def _build_map_keyboard() -> InlineKeyboardMarkup:
    base_url = settings.WEB_APP_URL.rstrip("/")
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🗺️ Открыть карту", web_app={"url": f"{base_url}/map"})]]
    )


async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Открываю карту Friendly Map!", reply_markup=_build_map_keyboard()
    )


map_command_handler = CommandHandler("map", map_command)
map_menu_handler = MessageHandler(filters.Regex("^(🗺 Карта|map)$"), map_command)
