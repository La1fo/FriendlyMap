from __future__ import annotations

from pathlib import Path

from telegram import InlineKeyboardMarkup, InputFile, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

BASE_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = BASE_DIR / "assets" / "sections"

SECTION_BANNERS = {
    "main_menu": {
        "title": "Friendly Map",
        "description": "Привет! Я Friendly Map Bot — помогу находить интересные места, сохранять локации и открывать карту.",
        "asset": "main_menu.png",
        "fallback_asset": "main_menu.svg",
    },
    "profile": {
        "title": "Профиль",
        "description": "Здесь собрана твоя статистика, прогресс и основная информация о профиле.",
        "asset": "profile.png",
        "fallback_asset": "profile.svg",
    },
    "achievements": {
        "title": "Достижения",
        "description": "Следи за прогрессом, открывай награды и собирай свои достижения.",
        "asset": "achievements.png",
        "fallback_asset": "achievements.svg",
    },
    "leaderboard": {
        "title": "Таблица лидеров",
        "description": "Смотри рейтинг пользователей и проверяй, кто сейчас в топе.",
        "asset": "leaderboard.png",
        "fallback_asset": "leaderboard.svg",
    },
    "faq": {
        "title": "FAQ",
        "description": "Здесь собраны ответы на частые вопросы и полезная информация по боту.",
        "asset": "faq.png",
        "fallback_asset": "faq.svg",
    },
    "moderation": {
        "title": "Модерация",
        "description": "Панель управления для проверки контента, заявок и административных действий.",
        "asset": "moderation.png",
        "fallback_asset": "moderation.svg",
    },
}


def get_section_banner(section: str) -> dict:
    return SECTION_BANNERS.get(section, SECTION_BANNERS["main_menu"])


def _resolve_asset(section: str) -> tuple[Path, bool]:
    item = get_section_banner(section)
    png = ASSETS_DIR / item["asset"]
    if png.exists():
        return png, True
    fallback = ASSETS_DIR / item["fallback_asset"]
    return fallback, False


async def send_section_banner(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    section: str,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str = ParseMode.HTML,
    store_message_key: str | None = None,
    delete_origin: bool = True,
):
    chat_id = update.effective_user.id
    origin_message = update.callback_query.message if update.callback_query else None

    if update.callback_query:
        await update.callback_query.answer()

    if delete_origin and origin_message:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=origin_message.message_id)
        except Exception:
            pass

    previous_banner_id = context.user_data.get("active_section_banner_message_id")
    origin_id = origin_message.message_id if origin_message else None
    if previous_banner_id and previous_banner_id != origin_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=previous_banner_id)
        except Exception:
            pass

    asset_path, can_send_photo = _resolve_asset(section)
    with asset_path.open("rb") as media:
        if can_send_photo:
            sent = await context.bot.send_photo(
                chat_id=chat_id,
                photo=InputFile(media, filename=asset_path.name),
                caption=caption,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
        else:
            sent = await context.bot.send_document(
                chat_id=chat_id,
                document=InputFile(media, filename=asset_path.name),
                caption=caption,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )

    context.user_data["active_section_banner_message_id"] = sent.message_id
    if store_message_key:
        context.user_data[store_message_key] = sent.message_id
    return sent
