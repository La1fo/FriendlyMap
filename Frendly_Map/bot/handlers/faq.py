from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
from bot.models.faq_entry import FaqEntry
from bot.utils.section_banners import get_section_banner, send_section_banner

FAQ_SITE_URL = "https://map.friendlymap.ru"
FAQ_SITE_HINT = "🌐 Подробные ответы на вопросы и чат с поддержкой доступны на сайте FriendlyMap."


def _render_faq_text(entries: list[FaqEntry]) -> str:
    lines = [FAQ_SITE_HINT]

    if not entries:
        lines.append("❓ Пока нет вопросов в FAQ.")
        return "\n\n".join(lines)

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
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🌐 Открыть сайт", url=FAQ_SITE_URL)],
                [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
            ]
        ),
    )


faq_handler = CommandHandler("faq", show_faq)
faq_callback_handler = CallbackQueryHandler(show_faq, pattern="^faq$")
faq_menu_handler = MessageHandler(filters.Regex("^(❓ FAQ|faq)$"), show_faq)
