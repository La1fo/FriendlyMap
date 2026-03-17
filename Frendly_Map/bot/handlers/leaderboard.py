from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
from bot.models.user import User
from bot.services.leaderboard_service import LeaderboardService
from shared.rank import get_rank_progress
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

    lines = ["🏆 Таблица лидеров (GP):"]
    for idx, user in enumerate(users, start=1):
        name = user.username or user.first_name or "Без имени"
        rank = get_rank_progress(user.total_gp)
        if idx > 1:
            lines.append("────────────")
        lines.append(
            f"{idx}. {name} — Общий GP: {rank['total_gp']} · {rank['rank_name']} · GP в ранге: {rank['gp_in_rank']}/100"
        )

    if position and total and current_user:
        me = update.effective_user
        name = me.username or me.first_name or "Ты"
        lines.extend([
            "",
            f"📍 {name}: место {position} из {total}",
            f"📍 Общий GP: {current_user.total_gp}",
            f"🏷️ Ранг: {get_rank_progress(current_user.total_gp)['rank_name']}",
            f"📈 GP в текущем ранге: {get_rank_progress(current_user.total_gp)['gp_in_rank']}/100",
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
