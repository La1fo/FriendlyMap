from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
from bot.models.faq_entry import FaqEntry
from bot.utils.section_banners import get_section_banner, send_section_banner


def _render_faq_text(entries: list[FaqEntry]) -> str:
    if not entries:
        return "❓ Пока нет вопросов в FAQ."

    lines = []
    for idx, entry in enumerate(entries, start=1):
        lines.append(f"<b>{idx}. {escape(entry.question)}</b>\n{escape(entry.answer)}")
    return "\n\n".join(lines)


async def show_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db_context() as db:
        entries = db.query(FaqEntry).order_by(FaqEntry.id.asc()).all()

    banner = get_section_banner("faq")
    details = _render_faq_text(entries)
    caption = f"<b>{banner['title']}</b>\n{banner['description']}\n\n{details}".strip()
    if len(caption) > 1024:
        caption = caption[:1021] + "..."

    await send_section_banner(
        update,
        context,
        "faq",
        caption,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]]),
    )


faq_handler = CommandHandler("faq", show_faq)
faq_callback_handler = CallbackQueryHandler(show_faq, pattern="^faq$")
faq_menu_handler = MessageHandler(filters.Regex("^(❓ FAQ|faq)$"), show_faq)
