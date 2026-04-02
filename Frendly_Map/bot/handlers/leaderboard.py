from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
from bot.models.user import User
from bot.services.leaderboard_service import LeaderboardService
from shared.rank import get_rank_progress
from bot.utils.section_banners import get_section_banner, send_section_banner

LEADERBOARD_SEPARATOR = "──────────────────────"


def _format_leaderboard_gp(rank_payload: dict[str, int | str]) -> str:
    return f"GP: {int(rank_payload['gp_in_rank'])}"


def build_leaderboard_caption(
    users: list[User],
    current_user: User | None,
    position: int,
    total: int,
    banner: dict[str, str],
    current_name: str,
) -> str:
    banner_caption = f"<b>{banner['title']}</b>\n{banner['description']}"
    if not users:
        return f"{banner_caption}\n\nРейтинг пока пуст 🤷"

    lines = ["🏆 Таблица лидеров (GP):"]
    for idx, user in enumerate(users, start=1):
        name = user.username or user.first_name or "Без имени"
        rank = get_rank_progress(user.total_gp, leaderboard_position=idx)
        if idx > 1:
            lines.append(LEADERBOARD_SEPARATOR)
        lines.append(f"{idx}. {name} — {rank['rank_name']} · {_format_leaderboard_gp(rank)}")

    if position and total and current_user:
        my_rank = get_rank_progress(current_user.total_gp, leaderboard_position=position)
        lines.extend([
            "",
            f"📍 {current_name}: место {position} из {total}",
            f"🏷️ {my_rank['rank_name']}",
            f"📈 {_format_leaderboard_gp(my_rank)}",
        ])

    caption = f"{banner_caption}\n\n" + "\n".join(lines)
    if len(caption) > 1024:
        caption = caption[:1021] + "..."
    return caption


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db_context() as db:
        LeaderboardService.ensure_sample_users(db)
        users = LeaderboardService.get_top_users(db, limit=10)
        position, total = LeaderboardService.get_user_position(db, update.effective_user.id)
        current_user = db.get(User, update.effective_user.id)

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]])
    banner = get_section_banner("leaderboard")
    me = update.effective_user
    name = me.username or me.first_name or "Ты"
    caption = build_leaderboard_caption(users, current_user, position, total, banner, name)

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
