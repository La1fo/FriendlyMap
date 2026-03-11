from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
from bot.models.user import User
from bot.services.leaderboard_service import LeaderboardService
from bot.utils.section_banners import get_section_banner, send_section_banner


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db_context() as db:
        LeaderboardService.ensure_sample_users(db)
        users = LeaderboardService.get_top_users(db, limit=10)
        position, total = LeaderboardService.get_user_position(db, update.effective_user.id)
        current_user = db.get(User, update.effective_user.id)

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]])
    banner = get_section_banner("leaderboard")
    banner_caption = f"<b>{banner['title']}</b>\n{banner['description']}"

    if not users:
        await send_section_banner(
            update,
            context,
            "leaderboard",
            f"{banner_caption}\n\nРейтинг пока пуст 🤷",
            reply_markup=back_kb,
        )
        return

    lines = ["🏆 Таблица лидеров (points):"]
    for idx, user in enumerate(users, start=1):
        name = user.username or user.first_name or "Без имени"
        rank_title = LeaderboardService.get_rank_title(user.points, idx)
        lines.append(f"{idx}. {name} — {user.points} ⭐ ({rank_title})")

    if position and total and current_user:
        me = update.effective_user
        name = me.username or me.first_name or "Ты"
        lines.extend([
            "",
            f"📍 {name}: место {position} из {total}",
            f"⭐ Твои points: {current_user.points}",
            f"🏷️ Твой ранг: {LeaderboardService.get_rank_title(current_user.points, position)}",
        ])

    caption = f"{banner_caption}\n\n" + "\n".join(lines)
    if len(caption) > 1024:
        caption = caption[:1021] + "..."

    await send_section_banner(
        update,
        context,
        "leaderboard",
        caption,
        reply_markup=back_kb,
    )


leaderboard_handler = CommandHandler("leaderboard", leaderboard)
leaderboard_menu_handler = MessageHandler(filters.Regex("^(🏆 Лидеры|leaderboard)$"), leaderboard)
leaderboard_callback_handler = CallbackQueryHandler(leaderboard, pattern="^leaderboard$")
