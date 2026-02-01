from datetime import datetime

from sqlalchemy import or_
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.database import get_db_context
from bot.handlers.moderation import send_pending_locations
from bot.models.location import Location
from bot.models.support_ticket import SupportTicket
from bot.models.user import User
from bot.utils.common import is_admin

POINTS_ACTION, POINTS_SEARCH, POINTS_SELECT_USER, POINTS_TYPE, POINTS_AMOUNT = range(5)
DEL_SEARCH, DEL_SELECT, DEL_REASON = range(5, 8)
TICKETS_MENU, TICKETS_SEARCH, TICKETS_SELECT = range(8, 11)


def _ensure_admin(update: Update) -> bool:
    return is_admin(update.effective_user.id)


def _moderation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📍 Модерация локаций", callback_data="mod_locations")],
        [InlineKeyboardButton("⚖️ Баллы и ранги", callback_data="mod_points")],
        [InlineKeyboardButton("🗑 Удаление локаций", callback_data="mod_delete_location")],
        [InlineKeyboardButton("🎫 Тикеты", callback_data="mod_tickets")],
    ])


async def moderation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        chat = update.callback_query.message
    else:
        chat = update.message

    if not _ensure_admin(update):
        await chat.reply_text("⛔ Только для модераторов.")
        return

    await chat.reply_text("⚙️ Панель модерации:", reply_markup=_moderation_keyboard())


async def moderation_locations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _ensure_admin(update):
        await query.message.reply_text("⛔ Только для модераторов.")
        return
    await send_pending_locations(query.message, update.effective_user.id)


async def points_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _ensure_admin(update):
        await query.message.reply_text("⛔ Только для модераторов.")
        return ConversationHandler.END

    context.user_data.pop("points_data", None)
    await query.message.reply_text(
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ Добавить", callback_data="points_add"),
                InlineKeyboardButton("➖ Списать", callback_data="points_sub"),
            ]
        ])
    )
    return POINTS_ACTION


async def points_choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = "add" if query.data == "points_add" else "sub"
    context.user_data["points_data"] = {"action": action}
    await query.message.reply_text("Введите @username или ID пользователя для поиска:")
    return POINTS_SEARCH


async def points_search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    term = update.message.text.strip()
    with get_db_context() as db:
        if term.isdigit():
            users = db.query(User).filter(User.id == int(term)).all()
        else:
            users = db.query(User).filter(
                or_(
                    User.username.ilike(f"%{term}%"),
                    User.first_name.ilike(f"%{term}%"),
                )
            ).limit(10).all()

    if not users:
        await update.message.reply_text("Пользователь не найден. Попробуйте снова:")
        return POINTS_SEARCH

    keyboard = [
        [InlineKeyboardButton(
            f"{user.username or user.first_name or 'Без имени'} ({user.id})",
            callback_data=f"points_user_{user.id}"
        )]
        for user in users
    ]
    await update.message.reply_text(
        "Выберите пользователя:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return POINTS_SELECT_USER


async def points_select_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[-1])
    context.user_data.setdefault("points_data", {})["user_id"] = user_id
    await query.message.reply_text(
        "Какие баллы изменяем?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⭐ Обычные", callback_data="points_type_regular"),
                InlineKeyboardButton("🎯 Ранговые", callback_data="points_type_rank"),
            ]
        ])
    )
    return POINTS_TYPE


async def points_choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    points_type = "regular" if query.data == "points_type_regular" else "rank"
    context.user_data.setdefault("points_data", {})["type"] = points_type
    await query.message.reply_text("Введите число баллов:")
    return POINTS_AMOUNT


async def points_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data.get("points_data", {})
    if "user_id" not in data:
        await update.message.reply_text("⚠️ Пользователь не выбран.")
        return ConversationHandler.END

    try:
        amount = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Введите целое число:")
        return POINTS_AMOUNT

    delta = amount if data.get("action") == "add" else -amount
    with get_db_context() as db:
        user = db.query(User).filter(User.id == data["user_id"]).first()
        if not user:
            await update.message.reply_text("⚠️ Пользователь не найден.")
            return ConversationHandler.END

        if data.get("type") == "rank":
            user.pts = user.pts + delta
            new_value = user.pts
            label = "ранговых"
        else:
            user.points = max(user.points + delta, 0)
            new_value = user.points
            label = "обычных"
        db.commit()

    await update.message.reply_text(
        f"✅ Готово. Новый баланс {label} баллов: {new_value}"
    )
    context.user_data.pop("points_data", None)
    return ConversationHandler.END


async def delete_location_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _ensure_admin(update):
        await query.message.reply_text("⛔ Только для модераторов.")
        return ConversationHandler.END

    await query.message.reply_text("Введите название или ID локации для поиска:")
    return DEL_SEARCH


async def delete_location_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    term = update.message.text.strip()
    with get_db_context() as db:
        if term.isdigit():
            locations = db.query(Location).filter(
                Location.id == int(term),
                Location.status != "deleted"
            ).all()
        else:
            locations = db.query(Location).filter(
                Location.name.ilike(f"%{term}%"),
                Location.status != "deleted"
            ).limit(10).all()

    if not locations:
        await update.message.reply_text("Локации не найдены. Попробуйте снова:")
        return DEL_SEARCH

    keyboard = [
        [InlineKeyboardButton(f"{loc.name} (#{loc.id})", callback_data=f"del_loc_{loc.id}")]
        for loc in locations
    ]
    await update.message.reply_text("Выберите локацию:", reply_markup=InlineKeyboardMarkup(keyboard))
    return DEL_SELECT


async def delete_location_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loc_id = int(query.data.split("_")[-1])
    context.user_data["delete_loc_id"] = loc_id
    await query.message.reply_text("Укажите причину удаления:")
    return DEL_REASON


async def delete_location_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc_id = context.user_data.get("delete_loc_id")
    if not loc_id:
        await update.message.reply_text("⚠️ Локация не выбрана.")
        return ConversationHandler.END

    reason = update.message.text.strip()
    with get_db_context() as db:
        loc = db.query(Location).filter(Location.id == loc_id).first()
        if not loc:
            await update.message.reply_text("⚠️ Локация не найдена.")
            return ConversationHandler.END
        loc.status = "deleted"
        loc.moderation_comment = reason
        loc.moderated_at = datetime.utcnow()
        loc.approved_by = update.effective_user.id
        db.commit()

    context.user_data.pop("delete_loc_id", None)
    await update.message.reply_text("✅ Локация удалена и отмечена причиной.")
    return ConversationHandler.END


async def tickets_menu_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _ensure_admin(update):
        await query.message.reply_text("⛔ Только для модераторов.")
        return ConversationHandler.END

    await query.message.reply_text(
        "Выберите раздел тикетов:",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🟢 Активные", callback_data="tickets_active"),
                InlineKeyboardButton("📦 Архив", callback_data="tickets_archive"),
            ]
        ])
    )
    return TICKETS_MENU


async def tickets_choose_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    status = "open" if query.data == "tickets_active" else "closed"
    context.user_data["tickets_status"] = status
    await query.message.reply_text("Введите строку поиска (ID или username), или '-' чтобы показать все:")
    return TICKETS_SEARCH


async def tickets_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    term = update.message.text.strip()
    status = context.user_data.get("tickets_status", "open")
    with get_db_context() as db:
        query = db.query(SupportTicket, User).join(User, SupportTicket.user_id == User.id)
        query = query.filter(SupportTicket.status == status)
        if term != "-":
            if term.isdigit():
                query = query.filter(SupportTicket.id == int(term))
            else:
                query = query.filter(User.username.ilike(f"%{term}%"))
        results = query.order_by(SupportTicket.created_at.desc()).limit(15).all()

    if not results:
        await update.message.reply_text("Тикеты не найдены. Попробуйте снова:")
        return TICKETS_SEARCH

    keyboard = [
        [InlineKeyboardButton(
            f"#{ticket.id} · {user.username or user.first_name or user.id}",
            callback_data=f"ticket_select_{ticket.id}"
        )]
        for ticket, user in results
    ]
    await update.message.reply_text("Выберите тикет:", reply_markup=InlineKeyboardMarkup(keyboard))
    return TICKETS_SELECT


async def tickets_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split("_")[-1])
    context.user_data["moderation_ticket_id"] = ticket_id

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        user = db.query(User).filter(User.id == ticket.user_id).first() if ticket else None

    if not ticket:
        await query.message.reply_text("⚠️ Тикет не найден.")
        return ConversationHandler.END

    user_label = user.username or user.first_name or ticket.user_id
    await query.message.reply_text(
        f"💬 Чат тикета #{ticket_id} с пользователем {user_label}.\n"
        "Напишите сообщение для ответа.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"ticket_close_{ticket_id}")],
            [InlineKeyboardButton("🔙 Назад к тикетам", callback_data="mod_tickets")]
        ])
    )
    return ConversationHandler.END


async def close_ticket_by_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _ensure_admin(update):
        await query.message.reply_text("⛔ Только для модераторов.")
        return

    ticket_id = int(query.data.split("_")[-1])
    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket or ticket.status != "open":
            await query.message.reply_text("⚠️ Тикет уже закрыт или не найден.")
            return
        ticket.status = "closed"
        ticket.closed_at = datetime.utcnow()
        ticket.closed_by = update.effective_user.id
        user_id = ticket.user_id
        db.commit()

    if context.user_data.get("moderation_ticket_id") == ticket_id:
        context.user_data.pop("moderation_ticket_id", None)

    await query.message.reply_text("✅ Тикет закрыт и перемещен в архив.")
    await context.bot.send_message(
        chat_id=user_id,
        text=f"✅ Ваш тикет #{ticket_id} закрыт модератором и перемещен в архив.",
    )


moderation_menu_handler = CommandHandler("moderation", moderation_menu)
moderation_menu_callback = CallbackQueryHandler(moderation_menu, pattern="^moderation$")
moderation_locations_handler = CallbackQueryHandler(moderation_locations, pattern="^mod_locations$")

points_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(points_start, pattern="^mod_points$")],
    states={
        POINTS_ACTION: [CallbackQueryHandler(points_choose_action, pattern="^points_(add|sub)$")],
        POINTS_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, points_search_user)],
        POINTS_SELECT_USER: [CallbackQueryHandler(points_select_user, pattern="^points_user_\d+$")],
        POINTS_TYPE: [CallbackQueryHandler(points_choose_type, pattern="^points_type_(regular|rank)$")],
        POINTS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, points_apply)],
    },
    fallbacks=[CommandHandler("cancel", moderation_menu)],
    allow_reentry=True,
)

delete_location_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(delete_location_start, pattern="^mod_delete_location$")],
    states={
        DEL_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_location_search)],
        DEL_SELECT: [CallbackQueryHandler(delete_location_select, pattern="^del_loc_\d+$")],
        DEL_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_location_reason)],
    },
    fallbacks=[CommandHandler("cancel", moderation_menu)],
    allow_reentry=True,
)

tickets_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(tickets_menu_start, pattern="^mod_tickets$")],
    states={
        TICKETS_MENU: [CallbackQueryHandler(tickets_choose_section, pattern="^tickets_(active|archive)$")],
        TICKETS_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, tickets_search)],
        TICKETS_SELECT: [CallbackQueryHandler(tickets_select, pattern="^ticket_select_\d+$")],
    },
    fallbacks=[CommandHandler("cancel", moderation_menu)],
    allow_reentry=True,
)

moderation_close_ticket_handler = CallbackQueryHandler(close_ticket_by_moderator, pattern="^ticket_close_\d+$")
