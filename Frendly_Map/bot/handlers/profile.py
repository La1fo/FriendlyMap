from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
from bot.models.user import User
from bot.services.ticket_service import TicketService
from bot.utils.rank import get_user_rank_display

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with get_db_context() as db:
        user = db.query(User).filter(User.id == uid).first()
        tickets = TicketService.list_user_tickets(db, uid)

    if not user:
        await update.message.reply_text("Ошибка: профиль не найден 😢")
        return

    msg = (
        f"👤 Твой профиль\n\n"
        f"🌐 Ник: @{user.username or 'Не указан'}\n"
        f"⭐ Баллы: {user.points}\n"
        f"🏅 Ранг: {get_user_rank_display(user.points)}\n"
        f"📍 Одобрено локаций: {user.approved_locations}"
    )

    if tickets:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(f"Тикет #{t.id} ({t.status})", callback_data=f"ticket_view_{t.id}")]
             for t in tickets[:5]]
        )
        await update.message.reply_text(msg + "\n\n🎫 Твои тикеты:", reply_markup=kb)
    else:
        await update.message.reply_text(msg + "\n\n🎫 Тикетов пока нет.")

profile_handler = CommandHandler("profile", profile)
profile_menu_handler = MessageHandler(filters.Regex("^(👤 Профиль|profile)$"), profile)
