from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

from datetime import datetime
from bot.database import get_db_context
from bot.models.location import Location
from bot.models.user import User
from bot.utils.common import is_admin
from bot.services.achievements_manager import AchievementsManager


async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Только для модераторов.")
        return

    with get_db_context() as db:
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

    achievements = AchievementsManager()
    completed = []

    with get_db_context() as db:
        loc = db.query(Location).filter(Location.id == loc_id).first()

        if not loc:
            await query.edit_message_text("⚠️ Локация не найдена")
            return

        owner = db.query(User).filter(User.id == loc.user_id).first()
        # изменение статуса
        if action == "approve":
            loc.status = "approved"
            loc.approved_by = uid
            loc.moderated_at = datetime.utcnow()
            if owner:
                owner.points += 15
                owner.approved_locations += 1
                owner.moderation_locations = max(owner.moderation_locations - 1, 0)
                completed = achievements.apply_event(db, owner.id, "location_approved", 1)
            # +15 баллов
        elif action == "reject":
            loc.status = "rejected"
            loc.approved_by = uid
            loc.moderated_at = datetime.utcnow()
            if owner:
                owner.points = max(owner.points - 5, 0)
                owner.rejected_locations += 1
                owner.moderation_locations = max(owner.moderation_locations - 1, 0)
            # -5 баллов, но не меньше нуля

        db.commit()

        # уведомление пользователя при approve/reject
        if owner:
            if action == "approve":
                await context.bot.send_message(
                    chat_id=owner.id,
                    text=f"🎉 Твоя локация <b>{loc.name}</b> была <b>одобрена</b>!",
                    parse_mode="HTML"
                )
                if completed:
                    await context.bot.send_message(
                        chat_id=owner.id,
                        text=achievements.format_completion_message(completed)
                    )
            else:
                await context.bot.send_message(
                    chat_id=owner.id,
                    text=f"😕 Локация <b>{loc.name}</b> была <b>отклонена</b>.",
                    parse_mode="HTML"
                )

    await query.edit_message_text(f"Готово: {action} #{loc_id}")

pending_handler = CommandHandler("pending", pending)
moderation_callback_handler = CallbackQueryHandler(handle_callback, pattern="^(approve|reject)_[0-9]+$")
