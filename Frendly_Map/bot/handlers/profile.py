from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
from bot.models.user import User
from shared.rank import get_rank_progress
from bot.utils.section_banners import get_section_banner, send_section_banner


def _profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]])


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with get_db_context() as db:
        user = db.query(User).filter(User.id == uid).first()

    if not user:
        if update.callback_query:
            await update.callback_query.answer("Ошибка: профиль не найден 😢", show_alert=True)
        else:
            await update.message.reply_text("Ошибка: профиль не найден 😢")
        return

    banner = get_section_banner("profile")
    rank = get_rank_progress(user.total_gp)
    caption = (
        f"<b>{banner['title']}</b>\n{banner['description']}\n\n"
        f"🌐 Ник: @{user.username or 'Не указан'}\n"
        f"🪙 Монеты: {user.points}\n"
        f"🏅 {rank['rank_name']}\n"
        f"📈 GP в текущем ранге: {rank['gp_in_rank']}/100\n"
        f"📍 Общий GP: {rank['total_gp']}\n"
        f"📍 Одобрено локаций: {user.approved_locations}"
    )

    sent = await send_section_banner(
        update,
        context,
        "profile",
        caption,
        reply_markup=_profile_keyboard(),
        store_message_key="profile_menu_message_id",
    )
    context.user_data["profile_menu_message_id"] = sent.message_id


profile_handler = CommandHandler("profile", profile)
profile_menu_handler = MessageHandler(filters.Regex("^(👤 Профиль|profile)$"), profile)
profile_callback_handler = CallbackQueryHandler(profile, pattern="^profile$")
