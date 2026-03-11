import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
from bot.models.achievement import Achievement
from bot.services.achievements_manager import AchievementsManager
from bot.utils.section_banners import get_section_banner, send_section_banner


def _achievement_keyboard(active_view: str) -> InlineKeyboardMarkup:
    standard_mark = "✅ " if active_view == "standard" else ""
    ranked_mark = "✅ " if active_view == "ranked" else ""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{standard_mark}Постоянные", callback_data="achievements_standard"),
            InlineKeyboardButton(f"{ranked_mark}Временные", callback_data="achievements_ranked"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])


def _progress_bar(progress: int, target: int, width: int = 8) -> str:
    if target <= 0:
        target = 1
    ratio = max(0.0, min(progress / target, 1.0))
    filled = int(round(ratio * width))
    return "█" * filled + "░" * (width - filled)


async def achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    manager = AchievementsManager()
    view_type = "standard"
    if update.callback_query and update.callback_query.data in {"achievements_standard", "achievements_ranked"}:
        view_type = "ranked" if update.callback_query.data.endswith("ranked") else "standard"

    with get_db_context() as db:
        manager.ensure_definitions(db)
        current_season = manager.get_current_season(db)
        achievements_list = (
            db.query(Achievement)
            .filter(Achievement.type == view_type)
            .order_by(Achievement.id)
            .all()
        )

        header = "⏱️ Временные достижения" if view_type == "ranked" else "📌 Постоянные достижения"
        lines = [header]
        if view_type == "ranked":
            lines.extend([f"Сезон: <b>{current_season.key}</b>", ""])

        for idx, achievement in enumerate(achievements_list, start=1):
            if idx > 1:
                lines.append("────────────")
            season_id = current_season.id if achievement.type == "ranked" else None
            progress_entry = manager.get_user_progress(db, user_id, achievement, season_id=season_id)
            progress = progress_entry.progress if progress_entry else 0
            target = _get_target(achievement)
            completed = bool(progress_entry and progress_entry.is_completed)
            reward = f"+{achievement.points_reward}🪙"
            if achievement.type == "ranked" and achievement.pts_reward:
                reward += f", +{achievement.pts_reward}📍 GP"

            scale = _progress_bar(progress, target)
            lines.append(
                "\n".join([
                    f"{achievement.icon} <b>{achievement.name}</b>",
                    achievement.description,
                    f"Шкала: <b>{scale}</b>",
                    f"Прогресс: <b>{min(progress, target)}/{target}</b>",
                    f"Статус: <b>{'✅ выполнено' if completed else '⏳ в процессе'}</b>",
                    f"Награда: <b>{reward}</b>",
                ])
            )
            lines.append("")

    banner = get_section_banner("achievements")
    details = "\n".join(lines).strip() if lines else "Достижения не найдены."
    caption = f"<b>{banner['title']}</b>\n{banner['description']}\n\n{details}".strip()
    if len(caption) > 1024:
        caption = caption[:1021] + "..."

    await send_section_banner(
        update,
        context,
        "achievements",
        caption,
        reply_markup=_achievement_keyboard(view_type),
    )


def _get_target(achievement: Achievement) -> int:
    try:
        data = json.loads(achievement.conditions)
        return int(data.get("target", 1))
    except Exception:
        return 1


achievements_handler = CommandHandler("achievements", achievements)
achievements_menu_handler = MessageHandler(filters.Regex("^(🏆 Достижения|achievements)$"), achievements)
achievements_callback_handler = CallbackQueryHandler(achievements, pattern="^achievements(|_(standard|ranked))$")
