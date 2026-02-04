from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.database import get_db_context
from bot.services.moderation_service import send_pending_locations
from bot.models.location import Location
from bot.models.photo import Photo
from bot.models.support_ticket import SupportMessage, SupportTicket
from bot.models.user import User
from bot.utils.common import is_admin

POINTS_ACTION, POINTS_TYPE, POINTS_SELECT_USER, POINTS_AMOUNT, POINTS_CUSTOM = range(5)
DEL_SELECT = 5
TICKETS_MENU, TICKETS_SEARCH, TICKETS_SELECT = range(6, 9)


def _ensure_admin(update: Update) -> bool:
    return is_admin(update.effective_user.id)


def _moderation_keyboard(unread_tickets: bool) -> InlineKeyboardMarkup:
    tickets_label = "🎫 Тикеты"
    if unread_tickets:
        tickets_label += " 🔔"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📍 Модерация локаций", callback_data="mod_locations")],
        [InlineKeyboardButton("⚖️ Баллы и ранги", callback_data="mod_points")],
        [InlineKeyboardButton("🗑 Удаление локаций", callback_data="mod_delete_location")],
        [InlineKeyboardButton(tickets_label, callback_data="mod_tickets")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])


def _format_ticket_history(messages: list[SupportMessage]) -> str:
    if not messages:
        return "Сообщений пока нет."
    lines = []
    for msg in messages:
        who = "👤" if msg.sender_role == "user" else "👮"
        timestamp = msg.created_at.strftime("%d.%m %H:%M") if msg.created_at else ""
        lines.append(f"{who} {timestamp}\n{msg.message}")
    return "\n\n".join(lines)


def _ticket_actions_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["◀️ Назад", "✅ Закрыть тикет"]],
        resize_keyboard=True
    )


def _back_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["◀️ Назад"]], resize_keyboard=True)


async def _render_points_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db_context() as db:
        users = db.query(User).order_by(User.id.desc()).limit(20).all()

    if not users:
        await _show_moderation_menu(update, context)
        return

    keyboard = []
    for user in users:
        label = f"@{user.username}" if user.username else "Без ника"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"points_user_{user.id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="mod_points")])
    menu_message_id = context.user_data.get("moderation_menu_message_id")
    if menu_message_id:
        await context.bot.edit_message_text(
            "Выберите пользователя:",
            chat_id=update.effective_user.id,
            message_id=menu_message_id,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        sent = await update.message.reply_text(
            "Выберите пользователя:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data["moderation_menu_message_id"] = sent.message_id


async def _render_tickets_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_message_id = context.user_data.get("moderation_menu_message_id")
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 Активные", callback_data="tickets_active"),
            InlineKeyboardButton("📦 Архив", callback_data="tickets_archive"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="moderation")],
    ])
    if menu_message_id:
        await context.bot.edit_message_text(
            "Выберите раздел тикетов:",
            chat_id=update.effective_user.id,
            message_id=menu_message_id,
            reply_markup=keyboard
        )
    else:
        sent = await update.message.reply_text("Выберите раздел тикетов:", reply_markup=keyboard)
        context.user_data["moderation_menu_message_id"] = sent.message_id


async def _show_moderation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_message_id = context.user_data.get("moderation_menu_message_id")
    unread_tickets = bool(context.bot_data.get("mod_unread_tickets"))
    if menu_message_id:
        await context.bot.edit_message_text(
            "⚙️ Панель модерации:",
            chat_id=update.effective_user.id,
            message_id=menu_message_id,
            reply_markup=_moderation_keyboard(unread_tickets)
        )
    else:
        sent = await (update.message or update.callback_query.message).reply_text(
            "⚙️ Панель модерации:",
            reply_markup=_moderation_keyboard(unread_tickets)
        )
        context.user_data["moderation_menu_message_id"] = sent.message_id


async def moderation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        chat = update.callback_query.message
    else:
        chat = update.message

    if not _ensure_admin(update):
        await chat.reply_text("⛔ Только для модераторов.")
        return

    if update.callback_query:
        context.user_data["moderation_menu_message_id"] = update.callback_query.message.message_id
    await _show_moderation_menu(update, context)


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
    context.user_data["moderation_menu_message_id"] = query.message.message_id
    await query.edit_message_text(
        "Что сделать?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ Начислить", callback_data="points_add"),
                InlineKeyboardButton("➖ Списать", callback_data="points_sub"),
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data="moderation")],
        ])
    )
    return POINTS_ACTION


async def points_choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = "add" if query.data == "points_add" else "sub"
    context.user_data["points_data"] = {"action": action}
    await query.edit_message_text(
        "Что изменить?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⭐ Баллы", callback_data="points_type_regular"),
                InlineKeyboardButton("🎯 Ранговые очки", callback_data="points_type_rank"),
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data="mod_points")],
        ])
    )
    return POINTS_TYPE


async def points_select_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[-1])
    context.user_data.setdefault("points_data", {})["user_id"] = user_id
    action_label = "Начислить" if context.user_data.get("points_data", {}).get("action") == "add" else "Списать"
    type_label = "баллы" if context.user_data.get("points_data", {}).get("type") == "regular" else "ранговые очки"
    await query.edit_message_text(
        f"{action_label} {type_label}. Выберите количество:",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("1", callback_data="points_amount_1"),
                InlineKeyboardButton("5", callback_data="points_amount_5"),
                InlineKeyboardButton("10", callback_data="points_amount_10"),
            ],
            [
                InlineKeyboardButton("20", callback_data="points_amount_20"),
                InlineKeyboardButton("Другое", callback_data="points_amount_custom"),
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data="points_type_back")],
        ])
    )
    return POINTS_AMOUNT


async def points_choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    points_type = "regular" if query.data == "points_type_regular" else "rank"
    context.user_data.setdefault("points_data", {})["type"] = points_type
    await _render_points_users(update, context)
    return POINTS_SELECT_USER


def _apply_points_change(db, data: dict, amount: int):
    delta = amount if data.get("action") == "add" else -amount
    user = db.query(User).filter(User.id == data["user_id"]).first()
    if not user:
        return None, None

    if data.get("type") == "rank":
        user.pts = user.pts + delta
        new_value = user.pts
        label = "ранговых"
    else:
        user.points = max(user.points + delta, 0)
        new_value = user.points
        label = "обычных"
    db.commit()
    return new_value, label


async def points_apply(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int | None = None):
    data = context.user_data.get("points_data", {})
    if "user_id" not in data:
        await update.message.reply_text("⚠️ Пользователь не выбран.")
        return ConversationHandler.END

    if amount is None:
        try:
            amount = int(update.message.text.strip())
        except ValueError:
            await update.message.reply_text("Введите целое число:")
            return POINTS_CUSTOM

    with get_db_context() as db:
        new_value, label = _apply_points_change(db, data, amount)

    if new_value is None:
        await update.message.reply_text("⚠️ Пользователь не найден.")
        return ConversationHandler.END

    await update.message.reply_text(
        f"✅ Готово. Новый баланс {label} баллов: {new_value}",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.pop("points_data", None)
    await _render_points_users(update, context)
    return POINTS_SELECT_USER


async def points_amount_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split("_")[-1]
    if choice == "custom":
        await query.edit_message_text("Введите число:")
        return POINTS_CUSTOM
    amount = int(choice)
    data = context.user_data.get("points_data", {})
    with get_db_context() as db:
        new_value, label = _apply_points_change(db, data, amount)

    if new_value is None:
        await query.message.reply_text("⚠️ Пользователь не найден.")
        return ConversationHandler.END

    await query.message.reply_text(
        f"✅ Готово. Новый баланс {label} баллов: {new_value}",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.pop("points_data", None)
    await _render_points_users(update, context)
    return POINTS_SELECT_USER


async def points_type_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("points_data", None)
    await points_start(update, context)
    return POINTS_ACTION


async def delete_location_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _ensure_admin(update):
        await query.message.reply_text("⛔ Только для модераторов.")
        return ConversationHandler.END

    context.user_data["moderation_menu_message_id"] = query.message.message_id
    context.user_data["delete_locations_active"] = True
    await query.edit_message_text("Выберите локацию:", reply_markup=InlineKeyboardMarkup([]))
    await update.effective_message.reply_text(
        "Меню удаления локаций.",
        reply_markup=_back_reply_keyboard()
    )
    await render_delete_locations(update, context)
    return DEL_SELECT


async def render_delete_locations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db_context() as db:
        locations = db.query(Location).filter(Location.status != "deleted").limit(20).all()

    if not locations:
        menu_message_id = context.user_data.get("moderation_menu_message_id")
        if menu_message_id:
            await context.bot.edit_message_text(
                "Локаций нет.",
                chat_id=update.effective_user.id,
                message_id=menu_message_id,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад", callback_data="moderation")]
                ])
            )
        return

    keyboard = [
        [InlineKeyboardButton(f"{loc.name} (#{loc.id})", callback_data=f"del_loc_{loc.id}")]
        for loc in locations
    ]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="moderation")])
    menu_message_id = context.user_data.get("moderation_menu_message_id")
    if menu_message_id:
        await context.bot.edit_message_text(
            "Выберите локацию:",
            chat_id=update.effective_user.id,
            message_id=menu_message_id,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        target = update.message or (update.callback_query.message if update.callback_query else None)
        if target:
            sent = await target.reply_text(
                "Выберите локацию:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            context.user_data["moderation_menu_message_id"] = sent.message_id


async def delete_location_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loc_id = int(query.data.split("_")[-1])
    context.user_data["delete_loc_id"] = loc_id
    await query.edit_message_text(
        "Действия с локацией:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ℹ️ Подробнее", callback_data=f"del_loc_info_{loc_id}")],
            [InlineKeyboardButton("🗑 Удалить", callback_data=f"del_loc_confirm_{loc_id}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="mod_delete_location")],
        ])
    )
    return DEL_SELECT


async def delete_location_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loc_id = int(query.data.split("_")[-1])
    with get_db_context() as db:
        loc = db.query(Location).filter(Location.id == loc_id).first()
        photos = (
            db.query(Photo)
            .filter(Photo.location_id == loc_id)
            .order_by(Photo.order_index.asc())
            .all()
        ) if loc else []

    if not loc:
        await query.edit_message_text("⚠️ Локация не найдена.")
        return

    info = (
        f"📍 {loc.name}\n"
        f"📝 {loc.description or 'Без описания'}\n"
        f"🌍 {loc.latitude}, {loc.longitude}\n"
        f"🗺️ Статус: {loc.status}"
    )
    await query.edit_message_text(
        info,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data=f"del_loc_{loc_id}")],
        ])
    )
    for photo in photos[:5]:
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo.file_id)


async def delete_location_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loc_id = int(query.data.split("_")[-1])
    with get_db_context() as db:
        loc = db.query(Location).filter(Location.id == loc_id).first()
        if not loc:
            await query.edit_message_text("⚠️ Локация не найдена.")
            return
        loc.status = "deleted"
        loc.moderated_at = datetime.utcnow()
        loc.approved_by = update.effective_user.id
        db.commit()

    context.user_data.pop("delete_loc_id", None)
    await query.edit_message_text("✅ Локация удалена.")
    await render_delete_locations(update, context)


async def delete_locations_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("delete_locations_active"):
        return
    context.user_data.pop("delete_locations_active", None)
    await update.message.reply_text(" ", reply_markup=ReplyKeyboardRemove())
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass
    await _show_moderation_menu(update, context)


async def tickets_menu_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _ensure_admin(update):
        await query.message.reply_text("⛔ Только для модераторов.")
        return ConversationHandler.END

    context.user_data["moderation_menu_message_id"] = query.message.message_id
    await query.edit_message_text(
        "Выберите раздел тикетов:",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🟢 Активные", callback_data="tickets_active"),
                InlineKeyboardButton("📦 Архив", callback_data="tickets_archive"),
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data="moderation")],
        ])
    )
    return TICKETS_MENU


async def tickets_choose_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    status = "open" if query.data == "tickets_active" else "closed"
    context.user_data["tickets_status"] = status
    await query.edit_message_text("Введите строку поиска (ID или username), или '-' чтобы показать все:")
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

    unread = context.bot_data.get("mod_unread_tickets", set())
    keyboard = []
    for ticket, user in results:
        label = f"#{ticket.id} · {user.username or user.first_name or user.id}"
        if isinstance(unread, set) and ticket.id in unread:
            label += " 🔔"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"ticket_select_{ticket.id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="mod_tickets")])
    menu_message_id = context.user_data.get("moderation_menu_message_id")
    if menu_message_id:
        await context.bot.edit_message_text(
            "Выберите тикет:",
            chat_id=update.effective_user.id,
            message_id=menu_message_id,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text("Выберите тикет:", reply_markup=InlineKeyboardMarkup(keyboard))
    return TICKETS_SELECT


async def tickets_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split("_")[-1])
    context.user_data["moderation_ticket_id"] = ticket_id
    context.user_data["moderation_ticket_view"] = True
    unread = context.bot_data.get("mod_unread_tickets")
    if isinstance(unread, set) and ticket_id in unread:
        unread.discard(ticket_id)

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        user = db.query(User).filter(User.id == ticket.user_id).first() if ticket else None
        messages = (
            db.query(SupportMessage)
            .filter(SupportMessage.ticket_id == ticket_id)
            .order_by(SupportMessage.created_at.asc())
            .all()
        ) if ticket else []

    if not ticket:
        await query.message.reply_text("⚠️ Тикет не найден.")
        return ConversationHandler.END

    user_label = user.username or user.first_name or ticket.user_id
    history_text = _format_ticket_history(messages)
    await query.edit_message_text(
        f"💬 Тикет #{ticket_id} · {user_label}\n\n{history_text}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад к тикетам", callback_data="mod_tickets")]
        ])
    )
    await query.message.reply_text(
        "Выберите действие:",
        reply_markup=_ticket_actions_keyboard()
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


async def moderation_ticket_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("moderation_ticket_view"):
        return
    context.user_data.pop("moderation_ticket_view", None)
    await update.message.reply_text(" ", reply_markup=ReplyKeyboardRemove())
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass
    await _render_tickets_menu(update, context)


async def moderation_ticket_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("moderation_ticket_view"):
        return
    ticket_id = context.user_data.get("moderation_ticket_id")
    if not ticket_id:
        await update.message.reply_text("⚠️ Тикет не выбран.", reply_markup=ReplyKeyboardRemove())
        return
    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket or ticket.status != "open":
            await update.message.reply_text("⚠️ Тикет уже закрыт или не найден.", reply_markup=ReplyKeyboardRemove())
            return
        ticket.status = "closed"
        ticket.closed_at = datetime.utcnow()
        ticket.closed_by = update.effective_user.id
        user_id = ticket.user_id
        db.commit()

    context.user_data.pop("moderation_ticket_view", None)
    await update.message.reply_text(" ", reply_markup=ReplyKeyboardRemove())
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass
    await update.message.reply_text("✅ Тикет закрыт и перемещен в архив.")
    await context.bot.send_message(
        chat_id=user_id,
        text=f"✅ Ваш тикет #{ticket_id} закрыт модератором и перемещен в архив.",
    )
    await _render_tickets_menu(update, context)


moderation_menu_handler = CommandHandler("moderation", moderation_menu)
moderation_menu_callback = CallbackQueryHandler(moderation_menu, pattern="^moderation$")
moderation_locations_handler = CallbackQueryHandler(moderation_locations, pattern="^mod_locations$")

points_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(points_start, pattern="^mod_points$")],
    states={
        POINTS_ACTION: [CallbackQueryHandler(points_choose_action, pattern="^points_(add|sub)$")],
        POINTS_TYPE: [
            CallbackQueryHandler(points_choose_type, pattern="^points_type_(regular|rank)$"),
            CallbackQueryHandler(points_type_back, pattern="^points_type_back$"),
        ],
        POINTS_SELECT_USER: [CallbackQueryHandler(points_select_user, pattern="^points_user_\\d+$")],
        POINTS_AMOUNT: [CallbackQueryHandler(points_amount_choice, pattern="^points_amount_")],
        POINTS_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, points_apply)],
    },
    fallbacks=[CommandHandler("cancel", moderation_menu)],
    allow_reentry=True,
)

delete_location_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(delete_location_start, pattern="^mod_delete_location$")],
    states={
        DEL_SELECT: [
            CallbackQueryHandler(delete_location_select, pattern="^del_loc_\\d+$"),
            CallbackQueryHandler(delete_location_info, pattern="^del_loc_info_\\d+$"),
            CallbackQueryHandler(delete_location_confirm, pattern="^del_loc_confirm_\\d+$"),
        ],
    },
    fallbacks=[CommandHandler("cancel", moderation_menu)],
    allow_reentry=True,
)

tickets_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(tickets_menu_start, pattern="^mod_tickets$")],
    states={
        TICKETS_MENU: [CallbackQueryHandler(tickets_choose_section, pattern="^tickets_(active|archive)$")],
        TICKETS_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, tickets_search)],
        TICKETS_SELECT: [CallbackQueryHandler(tickets_select, pattern=r"^ticket_select_\d+$")],
    },
    fallbacks=[CommandHandler("cancel", moderation_menu)],
    allow_reentry=True,
)

moderation_close_ticket_handler = CallbackQueryHandler(close_ticket_by_moderator, pattern="^ticket_close_\\d+$")
moderation_ticket_back_handler = MessageHandler(filters.Regex("^◀️ Назад$"), moderation_ticket_back)
moderation_ticket_close_handler = MessageHandler(filters.Regex("^✅ Закрыть тикет$"), moderation_ticket_close)
moderation_delete_back_handler = MessageHandler(filters.Regex("^◀️ Назад$"), delete_locations_back)
