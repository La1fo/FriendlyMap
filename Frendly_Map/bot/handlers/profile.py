from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.database import get_db_session
from bot.models.user import User

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with next(get_db_session()) as db:
        user = db.query(User).filter(User.id == uid).first()

    if not user:
        await update.message.reply_text("Ошибка: профиль не найден 😢")
        return

    msg = (
        f"👤 Твой профиль\n\n"
        f"🌐 Ник: @{user.username or 'Не указан'}\n"
        f"⭐ Баллы: {user.points}\n"
        f"🏅 Ранг: {user.pts}\n"
        f"📍 Одобрено локаций: {user.approved_locations}"
    )

    await update.message.reply_text(msg)

profile_handler = CommandHandler("profile", profile)
