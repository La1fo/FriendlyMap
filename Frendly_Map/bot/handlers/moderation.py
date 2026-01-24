from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

from bot.database import get_db_session
from bot.models.location import Location
from bot.models.user import User
from bot.utils.common import is_admin
from bot.services.location_service import LocationService


async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Только для модераторов.")
        return

    with next(get_db_session()) as db:
        locations = db.query(Location).filter(Location.status == "pending").all()

    if not locations:
        await update.message.reply_text("🎉 Нет локаций на модерацию")
        return

    for loc in locations:
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✔️ Одобрить", callback_data=f"approve_{loc.id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{loc.id}")
            ]
        ])

        text = (
            f"📍 <b>{loc.name}</b>\n"
            f"📝 {loc.description or 'Без описания'}\n\n"
            f"👤 Автор: <code>{loc.user_id}</code>\n"
            f"🌍 {loc.latitude}, {loc.longitude}"
        )

        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = update.effective_user.id
    if not is_admin(uid):
        await query.edit_message_text("⛔ Доступ запрещен.")
        return

    action, loc_id = query.data.split("_")
    loc_id = int(loc_id)

    with next(get_db_session()) as db:
        service = LocationService(db)
        loc = db.query(Location).filter(Location.id == loc_id).first()

        if not loc:
            await query.edit_message_text("⚠️ Локация не найдена")
            return

        # изменение статуса
        if action == "approve":
            loc.status = "approved"
            # +15 баллов
            user.points += 15
        elif action == "reject":
            loc.status = "rejected"
            # -5 баллов, но не меньше нуля
            user.points = max(user.points - 5, 0)

        db.commit()

        # уведомление пользователя при approve/reject
        user = db.query(User).filter(User.id == loc.user_id).first()
        if user:
            if action == "approve":
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"🎉 Твоя локация <b>{loc.name}</b> была <b>одобрена</b>!",
                    parse_mode="HTML"
                )
            else:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"😕 Локация <b>{loc.name}</b> была <b>отклонена</b>.",
                    parse_mode="HTML"
                )

    await query.edit_message_text(f"Готово: {action} #{loc_id}")

pending_handler = CommandHandler("pending", pending)
moderation_callback_handler = CallbackQueryHandler(handle_callback, pattern="^(approve|reject)_[0-9]+$")
