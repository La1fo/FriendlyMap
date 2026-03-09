import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
from bot.models.achievement import Achievement
from bot.services.achievements_manager import AchievementsManager
from bot.utils.section_banners import get_section_banner, send_section_banner


async def achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    manager = AchievementsManager()

    with get_db_context() as db:
        manager.ensure_definitions(db)
        current_season = manager.get_current_season(db)
        achievements_list = db.query(Achievement).order_by(Achievement.type, Achievement.id).all()

        lines = [
            f"Сезон: <b>{current_season.key}</b>",
            "",
        ]

        type_labels = {"ranked": "ранговое", "standard": "стандартное"}

        for achievement in achievements_list:
            season_id = current_season.id if achievement.type == "ranked" else None
            progress_entry = manager.get_user_progress(db, user_id, achievement, season_id=season_id)
            progress = progress_entry.progress if progress_entry else 0
            target = _get_target(achievement)
            status = "✅ выполнено" if progress_entry and progress_entry.is_completed else "⏳ в процессе"
            progress_text = f"{progress}/{target}" if target > 1 else ("готово" if progress >= 1 else "0/1")
            reward = f"+{achievement.points_reward}⭐"
            if achievement.type == "ranked" and achievement.pts_reward:
                reward += f", +{achievement.pts_reward}🎖️"

            lines.append(
                "\n".join([
                    f"{achievement.icon} <b>{achievement.name}</b>",
                    f"{achievement.description}",
                    f"Тип: <b>{type_labels.get(achievement.type, achievement.type)}</b>",
                    f"Прогресс: <b>{progress_text}</b>",
                    f"Статус: <b>{status}</b>",
                    f"Награда: <b>{reward}</b>",
                ])
            )
            lines.append("")

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]])
    banner = get_section_banner("achievements")
    await send_section_banner(
        update,
        context,
        "achievements",
        f"<b>{banner['title']}</b>",
    )
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="\n".join(lines).strip(),
        parse_mode="HTML",
        reply_markup=back_kb,
    )


def _get_target(achievement: Achievement) -> int:
    try:
        data = json.loads(achievement.conditions)
        return int(data.get("target", 1))
    except Exception:
        return 1


achievements_handler = CommandHandler("achievements", achievements)
achievements_menu_handler = MessageHandler(filters.Regex("^(🏆 Достижения|achievements)$"), achievements)
achievements_callback_handler = CallbackQueryHandler(achievements, pattern="^achievements$")
