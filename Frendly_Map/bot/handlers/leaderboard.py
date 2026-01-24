from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
from bot.models.user import User


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db_context() as db:
        users = db.query(User).order_by(User.points.desc()).limit(10).all()

    if not users:
        await update.message.reply_text("Рейтинг пока пуст 🤷")
        return

    lines = ["🏆 Топ-10 по баллам:"]
    for idx, user in enumerate(users, start=1):
        name = user.username or user.first_name or "Без имени"
        lines.append(f"{idx}. {name} — {user.points} ⭐")

    await update.message.reply_text("\n".join(lines))


leaderboard_handler = CommandHandler("leaderboard", leaderboard)
leaderboard_menu_handler = MessageHandler(filters.Regex("^(🏆 Рейтинг|leaderboard)$"), leaderboard)
