from __future__ import annotations

import logging
from pathlib import Path

from telegram import InlineKeyboardMarkup, InputFile, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = BASE_DIR / "assets" / "sections"

SECTION_BANNERS = {
    "main_menu": {
        "title": "Friendly Map",
        "description": "Привет! Я Friendly Map Bot — помогу находить интересные места, сохранять локации и открывать карту.",
        "asset": "main_menu.png",
    },
    "profile": {
        "title": "Профиль",
        "description": "Здесь собрана твоя статистика, прогресс и основная информация о профиле.",
        "asset": "profile.png",
    },
    "achievements": {
        "title": "Достижения",
        "description": "Следи за прогрессом, открывай награды и собирай свои достижения.",
        "asset": "achievements.png",
    },
    "leaderboard": {
        "title": "Таблица лидеров",
        "description": "Смотри рейтинг пользователей и проверяй, кто сейчас в топе.",
        "asset": "leaderboard.png",
    },
    "faq": {
        "title": "FAQ",
        "description": "Здесь собраны ответы на частые вопросы и полезная информация по боту.",
        "asset": "faq.png",
    },
    "moderation": {
        "title": "Модерация",
        "description": "Панель управления для проверки контента, заявок и административных действий.",
        "asset": "moderation.png",
    },
}


def get_section_banner(section: str) -> dict:
    return SECTION_BANNERS.get(section, SECTION_BANNERS["main_menu"])


def _resolve_banner_photo_path(section: str) -> Path:
    item = get_section_banner(section)
    photo_path = ASSETS_DIR / item["asset"]
    if not photo_path.exists():
        message = (
            f"Section banner is missing: section='{section}', expected_path='{photo_path}'. "
            "Banner images must be provided as PNG files in bot/assets/sections/."
        )
        logger.error(message)
        raise FileNotFoundError(message)

    if photo_path.suffix.lower() != ".png":
        message = (
            f"Invalid section banner format for section='{section}': '{photo_path.name}'. "
            "Only PNG files are supported for section banners."
        )
        logger.error(message)
        raise ValueError(message)

    return photo_path


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
    chat_id = update.effective_chat.id
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

    try:
        photo_path = _resolve_banner_photo_path(section)
    except (FileNotFoundError, ValueError) as exc:
        logger.exception("Failed to resolve section banner", exc_info=exc)
        fallback_text = (
            f"{caption}\n\n"
            "⚠️ Баннер временно недоступен. "
            "Проверьте локальные PNG-ассеты в bot/assets/sections/."
        )
        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=fallback_text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        context.user_data["active_section_banner_message_id"] = sent.message_id
        if store_message_key:
            context.user_data[store_message_key] = sent.message_id
        return sent

    with photo_path.open("rb") as media:
        sent = await context.bot.send_photo(
            chat_id=chat_id,
            photo=InputFile(media, filename=photo_path.name),
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    context.user_data["active_section_banner_message_id"] = sent.message_id
    if store_message_key:
        context.user_data[store_message_key] = sent.message_id
    return sent
