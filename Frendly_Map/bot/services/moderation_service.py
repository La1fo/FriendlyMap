from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.database import get_db_context
from bot.models.location import Location
from bot.models.user import User
from bot.utils.common import is_admin


async def send_pending_locations(chat: Message, user_id: int):
    if not is_admin(user_id):
        await chat.reply_text("⛔ Только для модераторов.")
        return

    with get_db_context() as db:
        locations = db.query(Location).filter(Location.status == "pending").all()

    if not locations:
        await chat.reply_text("🎉 Нет локаций на модерацию")
        return

    for loc in locations:
        owner_name = "Без ника"
        with get_db_context() as db:
            owner = db.query(User).filter(User.id == loc.user_id).first()
            if owner and owner.username:
                owner_name = f"@{owner.username}"

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✔️ Одобрить", callback_data=f"approve_{loc.id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{loc.id}"),
            ],
            [
                InlineKeyboardButton("ℹ️ Подробнее", callback_data=f"loc_detail_{loc.id}"),
                InlineKeyboardButton("◀️ Назад", callback_data="moderation"),
            ],
        ])

        text = (
            f"📍 <b>{loc.name}</b>\n"
            f"📝 {loc.description or 'Без описания'}\n\n"
            f"👤 Автор: {owner_name}\n"
            f"🌍 {loc.latitude}, {loc.longitude}"
        )

        await chat.reply_text(text, reply_markup=kb, parse_mode="HTML")
