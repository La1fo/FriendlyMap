from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.database import get_db_context
from bot.keyboards.main_menu import get_main_menu
from bot.utils.section_banners import get_section_banner, send_section_banner
from bot.utils.users import get_or_create_user


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    with get_db_context() as db:
        get_or_create_user(db, user)

    banner = get_section_banner("main_menu")
    caption = f"<b>{banner['title']}</b>\n\n{banner['description']}"
    await send_section_banner(
        update,
        context,
        "main_menu",
        caption,
        reply_markup=get_main_menu(user.id),
        store_message_key="main_menu_message_id",
        delete_origin=False,
    )


start_handler = CommandHandler("start", start)
