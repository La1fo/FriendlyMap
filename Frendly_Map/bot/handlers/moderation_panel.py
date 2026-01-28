from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.database import get_db_context
from bot.models.location import Location
from bot.models.photo import Photo
from bot.models.user import User
from bot.services.achievements_manager import AchievementsManager
from bot.services.moderation_service import ModerationService
from bot.services.ticket_service import TicketService
from bot.utils.common import is_moderator

MENU, REJECT_REASON, DELETE_REASON, DELETE_CONFIRM, POINTS_USER, POINTS_ADJUST, POINTS_REASON = range(7)

MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🕒 На проверке", "🗑 Удаление локаций"],
        ["💎 Очки пользователей", "❓ FAQ"],
        ["🎫 Тикеты", "🔙 Назад"],
    ],
    resize_keyboard=True,
)


def _check_access(db, user_id: int) -> bool:
    return is_moderator(db, user_id)


async def open_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_db_context() as db:
        if not _check_access(db, user_id):
            await update.message.reply_text("⛔ Только для модераторов.")
            return ConversationHandler.END

    await update.message.reply_text("🛡 Панель модерации", reply_markup=MENU_KEYBOARD)
    return MENU


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "🕒 На проверке":
        return await show_pending(update, context)
    if text == "🗑 Удаление локаций":
        return await show_locations_for_delete(update, context)
    if text == "💎 Очки пользователей":
        await update.message.reply_text("Введите username или ID пользователя:")
        return POINTS_USER
    if text == "❓ FAQ":
        from bot.handlers.faq import list_faq
        return await list_faq(update, context)
    if text == "🎫 Тикеты":
        return await show_tickets(update, context)
    if text == "🔙 Назад":
        await update.message.reply_text("Возвращаюсь в главное меню.")
        return ConversationHandler.END
    await update.message.reply_text("Выберите пункт меню.")
    return MENU


async def show_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_db_context() as db:
        if not _check_access(db, user_id):
            await update.message.reply_text("⛔ Только для модераторов.")
            return ConversationHandler.END
        locations = (
            db.query(Location)
            .filter(Location.status == "pending", Location.is_deleted.is_(False))
            .order_by(Location.created_at.desc())
            .limit(10)
            .all()
        )
        locations_with_photos = [
            (loc, db.query(Photo).filter(Photo.location_id == loc.id).order_by(Photo.order_index).all())
            for loc in locations
        ]

    if not locations:
        await update.message.reply_text("🎉 Очередь пуста", reply_markup=MENU_KEYBOARD)
        return MENU

    for loc, photos in locations_with_photos:
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_approve_{loc.id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_reject_{loc.id}"),
            ]
        ])
        message = (
            f"📍 <b>{loc.name}</b> (ID: {loc.id})\n"
            f"📝 {loc.description or 'Без описания'}\n"
            f"📫 {loc.address or 'Без адреса'}\n"
            f"👤 Автор: <code>{loc.user_id}</code>\n"
            f"📅 {loc.created_at}\n"
            f"🌍 {loc.latitude}, {loc.longitude}"
        )
        if photos:
            await update.message.reply_photo(
                photos[0].file_id,
                caption=message,
                reply_markup=kb,
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(message, reply_markup=kb, parse_mode="HTML")
    return MENU


async def show_locations_for_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_db_context() as db:
        if not _check_access(db, user_id):
            await update.message.reply_text("⛔ Только для модераторов.")
            return ConversationHandler.END
        locations = (
            db.query(Location)
            .filter(Location.is_deleted.is_(False))
            .order_by(Location.created_at.desc())
            .limit(10)
            .all()
        )

    if not locations:
        await update.message.reply_text("Нет доступных локаций для удаления.", reply_markup=MENU_KEYBOARD)
        return MENU

    for loc in locations:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🗑 Удалить", callback_data=f"mod_delete_{loc.id}")]]
        )
        message = (
            f"📍 <b>{loc.name}</b> (ID: {loc.id})\n"
            f"Статус: {loc.status}\n"
            f"👤 Автор: <code>{loc.user_id}</code>\n"
            f"📅 {loc.created_at}"
        )
        await update.message.reply_text(message, reply_markup=kb, parse_mode="HTML")
    return MENU


async def show_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_db_context() as db:
        if not _check_access(db, user_id):
            await update.message.reply_text("⛔ Только для модераторов.")
            return ConversationHandler.END
        tickets = TicketService.list_open_tickets(db)

    if not tickets:
        await update.message.reply_text("Открытых тикетов нет.", reply_markup=MENU_KEYBOARD)
        return MENU

    for ticket in tickets[:10]:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Открыть", callback_data=f"ticket_open_{ticket.id}")]]
        )
        await update.message.reply_text(
            f"🎫 Тикет #{ticket.id} от пользователя {ticket.user_id} (статус: {ticket.status})",
            reply_markup=kb,
        )
    return MENU


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    user_id = update.effective_user.id
    with get_db_context() as db:
        if not _check_access(db, user_id):
            await query.edit_message_text("⛔ Доступ запрещен.")
            return ConversationHandler.END

    if data.startswith("mod_approve_"):
        loc_id = int(data.split("_")[-1])
        return await approve_location(update, context, loc_id)
    if data.startswith("mod_reject_"):
        loc_id = int(data.split("_")[-1])
        context.user_data["reject_location_id"] = loc_id
        await query.edit_message_text("Введите причину отклонения (можно '-' если без причины):")
        return REJECT_REASON
    if data.startswith("mod_delete_"):
        loc_id = int(data.split("_")[-1])
        context.user_data["delete_location_id"] = loc_id
        await query.edit_message_text("Введите причину удаления (можно '-' если без причины):")
        return DELETE_REASON

    return MENU


async def approve_location(update: Update, context: ContextTypes.DEFAULT_TYPE, loc_id: int):
    user_id = update.effective_user.id
    achievements = AchievementsManager()
    with get_db_context() as db:
        if not _check_access(db, user_id):
            await update.callback_query.edit_message_text("⛔ Доступ запрещен.")
            return ConversationHandler.END
        location = db.query(Location).filter(Location.id == loc_id, Location.is_deleted.is_(False)).first()
        if not location:
            await update.callback_query.edit_message_text("⚠️ Локация не найдена")
            return MENU
        ModerationService.approve_location(db, user_id, location)
        owner = db.get(User, location.user_id)
        completed = []
        if owner:
            owner.points += 15
            owner.approved_locations += 1
            owner.moderation_locations = max(owner.moderation_locations - 1, 0)
            completed = achievements.apply_event(db, owner.id, "location_approved", 1)
        db.commit()
    await update.callback_query.edit_message_text(f"✅ Локация #{loc_id} одобрена")
    if completed and owner:
        await context.bot.send_message(owner.id, achievements.format_completion_message(completed))
    return MENU


async def reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    loc_id = context.user_data.get("reject_location_id")
    if not loc_id:
        await update.message.reply_text("Не удалось определить локацию.", reply_markup=MENU_KEYBOARD)
        return MENU

    user_id = update.effective_user.id
    with get_db_context() as db:
        if not _check_access(db, user_id):
            await update.message.reply_text("⛔ Доступ запрещен.")
            return ConversationHandler.END
        location = db.query(Location).filter(Location.id == loc_id, Location.is_deleted.is_(False)).first()
        if not location:
            await update.message.reply_text("⚠️ Локация не найдена", reply_markup=MENU_KEYBOARD)
            return MENU
        ModerationService.reject_location(db, user_id, location, reason)
        owner = db.get(User, location.user_id)
        if owner:
            owner.points = max(owner.points - 5, 0)
            owner.rejected_locations += 1
            owner.moderation_locations = max(owner.moderation_locations - 1, 0)
        db.commit()

    context.user_data.pop("reject_location_id", None)
    await update.message.reply_text(f"❌ Локация #{loc_id} отклонена. Причина: {reason}", reply_markup=MENU_KEYBOARD)
    return MENU


async def delete_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    context.user_data["delete_reason"] = reason
    loc_id = context.user_data.get("delete_location_id")
    if not loc_id:
        await update.message.reply_text("Не удалось определить локацию.", reply_markup=MENU_KEYBOARD)
        return MENU

    await update.message.reply_text(
        f"Подтвердите удаление локации #{loc_id}: ответьте 'да' для подтверждения.",
        reply_markup=MENU_KEYBOARD,
    )
    return DELETE_CONFIRM


async def delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text != "да":
        await update.message.reply_text("Удаление отменено.", reply_markup=MENU_KEYBOARD)
        context.user_data.pop("delete_location_id", None)
        context.user_data.pop("delete_reason", None)
        return MENU

    loc_id = context.user_data.get("delete_location_id")
    reason = context.user_data.get("delete_reason", "-")
    user_id = update.effective_user.id

    with get_db_context() as db:
        if not _check_access(db, user_id):
            await update.message.reply_text("⛔ Доступ запрещен.")
            return ConversationHandler.END
        location = db.query(Location).filter(Location.id == loc_id, Location.is_deleted.is_(False)).first()
        if not location:
            await update.message.reply_text("⚠️ Локация не найдена", reply_markup=MENU_KEYBOARD)
            return MENU
        ModerationService.delete_location(db, user_id, location, reason)
        db.commit()

    context.user_data.pop("delete_location_id", None)
    context.user_data.pop("delete_reason", None)
    await update.message.reply_text(f"🗑 Локация #{loc_id} удалена. Причина: {reason}", reply_markup=MENU_KEYBOARD)
    return MENU


async def points_select_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identifier = update.message.text.strip().lstrip("@")
    with get_db_context() as db:
        if not _check_access(db, update.effective_user.id):
            await update.message.reply_text("⛔ Доступ запрещен.")
            return ConversationHandler.END
        user = db.query(User).filter(User.username == identifier).first()
        if identifier.isdigit():
            user = db.get(User, int(identifier)) or user

    if not user:
        await update.message.reply_text("Пользователь не найден. Попробуйте снова:")
        return POINTS_USER

    context.user_data["points_user_id"] = user.id
    await update.message.reply_text(
        f"Текущие значения для {user.username or user.first_name or user.id}:\n"
        f"pts: {user.pts}\npoints: {user.points}\n"
        "Введите изменения в формате: <pts_delta> <points_delta> (например: 10 -5)",
    )
    return POINTS_ADJUST


async def points_adjust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.strip().split()
    if len(parts) != 2:
        await update.message.reply_text("Нужно два числа: pts_delta points_delta")
        return POINTS_ADJUST
    try:
        delta_pts = int(parts[0])
        delta_points = int(parts[1])
    except ValueError:
        await update.message.reply_text("Введите корректные целые числа.")
        return POINTS_ADJUST

    if abs(delta_pts) > 100000 or abs(delta_points) > 100000:
        await update.message.reply_text("Слишком большое значение. Ограничение ±100000.")
        return POINTS_ADJUST

    context.user_data["delta_pts"] = delta_pts
    context.user_data["delta_points"] = delta_points
    await update.message.reply_text("Введите причину изменения очков:")
    return POINTS_REASON


async def points_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    user_id = context.user_data.get("points_user_id")
    delta_pts = context.user_data.get("delta_pts", 0)
    delta_points = context.user_data.get("delta_points", 0)

    if not user_id:
        await update.message.reply_text("Пользователь не выбран.")
        return MENU

    with get_db_context() as db:
        if not _check_access(db, update.effective_user.id):
            await update.message.reply_text("⛔ Доступ запрещен.")
            return ConversationHandler.END
        user = db.get(User, user_id)
        if not user:
            await update.message.reply_text("Пользователь не найден.")
            return MENU
        ModerationService.adjust_user_points(
            db,
            update.effective_user.id,
            user,
            delta_pts=delta_pts,
            delta_points=delta_points,
            reason=reason,
        )
        db.commit()

    context.user_data.pop("points_user_id", None)
    context.user_data.pop("delta_pts", None)
    context.user_data.pop("delta_points", None)
    await update.message.reply_text(
        f"✅ Очки изменены: pts {delta_pts:+}, points {delta_points:+}. Причина: {reason}",
        reply_markup=MENU_KEYBOARD,
    )
    return MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Модерация отменена.")
    return ConversationHandler.END


moderation_panel_handler = ConversationHandler(
    entry_points=[
        CommandHandler("moderation", open_menu),
        MessageHandler(filters.Regex("^(🛡 Модерация|moderation)$"), open_menu),
    ],
    states={
        MENU: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu),
            CallbackQueryHandler(handle_callback, pattern=r"^mod_(approve|reject|delete)_\d+$"),
        ],
        REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, reject_reason)],
        DELETE_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_reason)],
        DELETE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_confirm)],
        POINTS_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, points_select_user)],
        POINTS_ADJUST: [MessageHandler(filters.TEXT & ~filters.COMMAND, points_adjust)],
        POINTS_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, points_reason)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=True,
    allow_reentry=True,
)
