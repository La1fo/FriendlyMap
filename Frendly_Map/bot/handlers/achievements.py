import json
from html import escape
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
from bot.models.achievement import Achievement
from bot.services.achievements_manager import AchievementsManager
from bot.utils.section_banners import get_section_banner, send_section_banner

PAGE_SIZE = 5

def _achievement_keyboard(active_view: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    standard_mark = "✅ " if active_view == "standard" else ""
    ranked_mark = "✅ " if active_view == "ranked" else ""
    keyboard = [
        [
            InlineKeyboardButton(f"{standard_mark}Постоянные", callback_data="achievements_standard_page_1"),
            InlineKeyboardButton(f"{ranked_mark}Сезонные", callback_data="achievements_ranked_page_1"),
        ],
    ]
    if total_pages > 1:
        prev_page = max(1, page - 1)
        next_page = min(total_pages, page + 1)
        keyboard.append([
            InlineKeyboardButton("⬅️" if page > 1 else "·", callback_data=f"achievements_{active_view}_page_{prev_page}"),
            InlineKeyboardButton(f"{page}/{total_pages}", callback_data=f"achievements_{active_view}_page_{page}"),
            InlineKeyboardButton("➡️" if page < total_pages else "·", callback_data=f"achievements_{active_view}_page_{next_page}"),
        ])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="menu_back")])
    return InlineKeyboardMarkup(keyboard)


def _progress_bar(progress: int, target: int, width: int = 8) -> str:
    if target <= 0:
        target = 1
    ratio = max(0.0, min(progress / target, 1.0))
    filled = int(round(ratio * width))
    return "█" * filled + "░" * (width - filled)


def _safe_html_text(value: str | None) -> str:
    return escape(value or "", quote=False)

def _resolve_view_and_page(update: Update) -> tuple[str, int]:
    view_type = "standard"
    page = 1
    data = update.callback_query.data if update.callback_query else ""
    if not data:
        return view_type, page
    if data.startswith("achievements_ranked"):
        view_type = "ranked"
    elif data.startswith("achievements_standard"):
        view_type = "standard"
    if "_page_" in data:
        try:
            page = max(1, int(data.rsplit("_page_", 1)[1]))
        except ValueError:
            page = 1
    return view_type, page


async def achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    manager = AchievementsManager()
    view_type, page = _resolve_view_and_page(update)

    with get_db_context() as db:
        manager.ensure_definitions(db)
        current_season = manager.get_current_season(db)
        achievements_list = (
            db.query(Achievement)
            .filter(Achievement.type == view_type)
            .order_by(Achievement.id)
            .all()
        )

        total_items = len(achievements_list)
        total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, total_pages)
        start = (page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        page_items = achievements_list[start:end]

        header = "⏱️ Сезонные достижения" if view_type == "ranked" else "📌 Постоянные достижения"
        lines = [header]
        if view_type == "ranked":
            lines.extend([f"Сезон: {_safe_html_text(current_season.key)}", ""])

        for idx, achievement in enumerate(page_items, start=1):
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
            safe_name = _safe_html_text(achievement.name)
            safe_description = _safe_html_text(achievement.description)
            lines.append(
                "\n".join([
                    f"{achievement.icon} {safe_name}",
                    safe_description,
                    f"Шкала: {scale}",
                    f"Прогресс: {min(progress, target)}/{target}",
                    f"Статус: {'✅ выполнено' if completed else '⏳ в процессе'}",
                    f"Награда: {reward}",
                ])
            )
            lines.append("")

    banner = get_section_banner("achievements")
    details = "\n".join(lines).strip() if lines else "Достижения не найдены."
    safe_title = _safe_html_text(banner["title"])
    safe_description = _safe_html_text(banner["description"])
    caption = f"<b>{safe_title}</b>\n{safe_description}\n\n{details}".strip()
    if len(caption) > 1024:
        caption = caption[:1021] + "..."

    await send_section_banner(
        update,
        context,
        "achievements",
        caption,
        reply_markup=_achievement_keyboard(view_type, page, total_pages),
    )


def _get_target(achievement: Achievement) -> int:
    try:
        data = json.loads(achievement.conditions)
        return int(data.get("target", 1))
    except Exception:
        return 1


achievements_handler = CommandHandler("achievements", achievements)
achievements_menu_handler = MessageHandler(filters.Regex("^(🏆 Достижения|achievements)$"), achievements)
achievements_callback_handler = CallbackQueryHandler(
    achievements,
    pattern=r"^achievements(|_(standard|ranked)(|_page_\d+))$",
)
