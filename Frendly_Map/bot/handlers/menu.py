from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from bot.keyboards.main_menu import get_main_menu
from bot.utils.section_banners import get_section_banner, send_section_banner


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    banner = get_section_banner("main_menu")
    caption = f"<b>{banner['title']}</b>\n\n{banner['description']}"
    await send_section_banner(
        update,
        context,
        "main_menu",
        caption,
        reply_markup=get_main_menu(update.effective_user.id),
        store_message_key="main_menu_message_id",
    )


main_menu_callback_handler = CallbackQueryHandler(show_main_menu, pattern="^menu_back$")
