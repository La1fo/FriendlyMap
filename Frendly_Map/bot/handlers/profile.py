from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters

from bot.database import get_db_context
from bot.models.support_ticket import SupportTicket
from bot.models.user import User
from bot.utils.rank import get_user_rank_display


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        chat = update.callback_query.message
    else:
        chat = update.message

    uid = update.effective_user.id
    with get_db_context() as db:
        user = db.query(User).filter(User.id == uid).first()
        active_ticket = (
            db.query(SupportTicket)
            .filter(SupportTicket.user_id == uid, SupportTicket.status == "open")
            .first()
        )
        archived_tickets = (
            db.query(SupportTicket)
            .filter(SupportTicket.user_id == uid, SupportTicket.status == "closed")
            .order_by(SupportTicket.closed_at.desc())
            .limit(5)
            .all()
        )

    if not user:
        await chat.reply_text("Ошибка: профиль не найден 😢")
        return

    msg = (
        f"👤 Твой профиль\n\n"
        f"🌐 Ник: @{user.username or 'Не указан'}\n"
        f"⭐ Баллы: {user.points}\n"
        f"🎯 Ранговые очки: {user.pts}\n"
        f"🏅 Ранг: {get_user_rank_display(user.points)}\n"
        f"📍 Одобрено локаций: {user.approved_locations}"
    )

    if active_ticket:
        msg += f"\n\n🟢 Активный тикет: #{active_ticket.id}"

    if archived_tickets:
        archive_lines = ["\n📦 Архив тикетов:"]
        for ticket in archived_tickets:
            closed_at = ticket.closed_at.strftime("%d.%m.%Y") if ticket.closed_at else "-"
            archive_lines.append(f"• #{ticket.id} закрыт {closed_at}")
        msg += "\n".join(archive_lines)

    keyboard = None
    if active_ticket:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Перейти в чат", callback_data=f"support_chat_{active_ticket.id}")],
            [InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"support_close_{active_ticket.id}")]
        ])

    await chat.reply_text(msg, reply_markup=keyboard)


profile_handler = CommandHandler("profile", profile)
profile_menu_handler = MessageHandler(filters.Regex("^(👤 Профиль|profile)$"), profile)
profile_callback_handler = CallbackQueryHandler(profile, pattern="^profile$")
