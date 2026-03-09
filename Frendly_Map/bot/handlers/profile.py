from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
from bot.models.user import User
from bot.utils.rank import get_user_rank_display


def _profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]])


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        context.user_data["profile_menu_message_id"] = query.message.message_id

    uid = update.effective_user.id
    with get_db_context() as db:
        user = db.query(User).filter(User.id == uid).first()

    if not user:
        if query:
            await query.edit_message_text("Ошибка: профиль не найден 😢")
        else:
            await update.message.reply_text("Ошибка: профиль не найден 😢")
        return

    msg = (
        f"👤 Твой профиль\n\n"
        f"🌐 Ник: @{user.username or 'Не указан'}\n"
        f"⭐ Баллы: {user.points}\n"
        f"🎯 Ранговые очки: {user.pts}\n"
        f"🏅 Ранг: {get_user_rank_display(user.points)}\n"
        f"📍 Одобрено локаций: {user.approved_locations}"
    )

    if query:
        await query.edit_message_text(msg, reply_markup=_profile_keyboard())
    else:
        sent = await update.message.reply_text(msg, reply_markup=_profile_keyboard())
        context.user_data["profile_menu_message_id"] = sent.message_id


profile_handler = CommandHandler("profile", profile)
profile_menu_handler = MessageHandler(filters.Regex("^(👤 Профиль|profile)$"), profile)
profile_callback_handler = CallbackQueryHandler(profile, pattern="^profile$")
