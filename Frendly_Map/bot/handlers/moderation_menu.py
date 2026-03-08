from datetime import datetime
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.database import get_db_context
from bot.models.location import Location
from bot.models.photo import Photo
from bot.models.support_ticket import (
    SUPPORT_ACTIVE_STATUSES,
    SUPPORT_STATUS_CLOSED,
    SUPPORT_STATUS_IN_PROGRESS,
    SUPPORT_STATUS_NEW,
    SUPPORT_STATUS_WAITING_USER,
    SupportMessage,
    SupportTicket,
)
from bot.services.support_state import (
    get_session_mode,
    has_unread_moderation_tickets,
    set_active_ticket_id,
    set_session_mode,
)
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
        if msg.message_type == "photo":
            body = f"[Фото] {msg.message or ''}".strip()
        elif msg.message_type == "document":
            filename = f" ({msg.file_name})" if msg.file_name else ""
            body = f"[Документ{filename}] {msg.message or ''}".strip()
        else:
            body = msg.message
        lines.append(f"{who} {timestamp}\n{body}")
    return "\n\n".join(lines)


def _serialize_support_message(msg: SupportMessage) -> dict[str, Any]:
    return {
        "id": msg.id,
        "sender_role": msg.sender_role,
        "created_at": msg.created_at,
        "message_type": msg.message_type,
        "message": msg.message,
        "file_id": msg.file_id,
        "file_name": msg.file_name,
    }


def _format_ticket_history_payload(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return "Сообщений пока нет."

    lines = []
    for msg in messages:
        who = "👤" if msg["sender_role"] == "user" else "👮"
        created_at = msg.get("created_at")
        timestamp = created_at.strftime("%d.%m %H:%M") if created_at else ""
        if msg["message_type"] == "photo":
            body = f"[Фото] {msg.get('message') or ''}".strip()
        elif msg["message_type"] == "document":
            filename = f" ({msg.get('file_name')})" if msg.get("file_name") else ""
            body = f"[Документ{filename}] {msg.get('message') or ''}".strip()
        else:
            body = msg.get("message")
        lines.append(f"{who} {timestamp}\n{body}")
    return "\n\n".join(lines)


def _build_user_label(username: str | None, first_name: str | None, user_id: int) -> str:
    return username or first_name or str(user_id)


def _attachments_keyboard(messages: list[SupportMessage]) -> InlineKeyboardMarkup | None:
    attachments = [m for m in messages if m.message_type in {"photo", "document"} and m.file_id]
    if not attachments:
        return None

    attachments = attachments[-5:]
    rows = []
    for msg in attachments:
        icon = "🖼" if msg.message_type == "photo" else "📄"
        rows.append([InlineKeyboardButton(f"{icon} Вложение #{msg.id}", callback_data=f"mod_attach_{msg.id}")])
    rows.append([InlineKeyboardButton("🔙 Назад к тикетам", callback_data="mod_tickets")])
    return InlineKeyboardMarkup(rows)




async def _safe_edit_menu_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    text_value: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    try:
        await context.bot.edit_message_text(
            text_value,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )
        return True
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            return False
        raise


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
    header = "Выберите пользователя:"
    flash = context.user_data.pop("points_flash", None)
    if flash:
        header = f"{flash}\n\nВыберите пользователя:"

    if menu_message_id:
        await context.bot.edit_message_text(
            header,
            chat_id=update.effective_user.id,
            message_id=menu_message_id,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        sent = await update.message.reply_text(
            header,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data["moderation_menu_message_id"] = sent.message_id


async def _render_tickets_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_message_id = context.user_data.get("moderation_menu_message_id")
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🆕 Новые", callback_data="tickets_new"),
            InlineKeyboardButton("🛠 В работе", callback_data="tickets_in_progress"),
        ],
        [
            InlineKeyboardButton("⏳ Ожидают пользователя", callback_data="tickets_waiting_user"),
            InlineKeyboardButton("📦 Архив", callback_data="tickets_closed"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="moderation")],
    ])
    if menu_message_id:
        await _safe_edit_menu_message(
            context,
            chat_id=update.effective_user.id,
            message_id=menu_message_id,
            text_value="Выберите раздел тикетов:",
            reply_markup=keyboard,
        )
    else:
        sent = await update.message.reply_text("Выберите раздел тикетов:", reply_markup=keyboard)
        context.user_data["moderation_menu_message_id"] = sent.message_id


async def _render_tickets_list(update: Update, context: ContextTypes.DEFAULT_TYPE, status: str):
    with get_db_context() as db:
        query = db.query(SupportTicket, User).join(User, SupportTicket.user_id == User.id)
        status_map = {
            "new": SUPPORT_STATUS_NEW,
            "in_progress": SUPPORT_STATUS_IN_PROGRESS,
            "waiting_user": SUPPORT_STATUS_WAITING_USER,
            "closed": SUPPORT_STATUS_CLOSED,
        }
        if status == "active":
            query = query.filter(SupportTicket.status.in_(SUPPORT_ACTIVE_STATUSES))
        else:
            query = query.filter(SupportTicket.status == status_map.get(status, SUPPORT_STATUS_CLOSED))
        results = query.order_by(SupportTicket.created_at.desc()).limit(20).all()

    title_map = {
        "new": "Новые тикеты",
        "in_progress": "Тикеты в работе",
        "waiting_user": "Ожидают пользователя",
        "closed": "Архив тикетов",
        "active": "Активные тикеты",
    }
    title = title_map.get(status, "Тикеты")
    if not results:
        await _render_tickets_menu(update, context)
        return

    keyboard = []
    for ticket, user in results:
        label = f"#{ticket.id} · {user.username or user.first_name or user.id}"
        if ticket.unread_for_moderator:
            label += " 🔔"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"ticket_select_{status}_{ticket.id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="mod_tickets")])

    menu_message_id = context.user_data.get("moderation_menu_message_id")
    if menu_message_id:
        await _safe_edit_menu_message(
            context,
            chat_id=update.effective_user.id,
            message_id=menu_message_id,
            text_value=title,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        sent = await update.message.reply_text(title, reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["moderation_menu_message_id"] = sent.message_id


async def _show_moderation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_message_id = context.user_data.get("moderation_menu_message_id")
    with get_db_context() as db:
        unread_tickets = has_unread_moderation_tickets(db)
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
        await query.edit_message_text("⛔ Только для модераторов.")
        return

    with get_db_context() as db:
        locations = db.query(Location).filter(Location.status == "pending").order_by(Location.created_at.asc()).limit(20).all()

    if not locations:
        await query.edit_message_text(
            "📍 Модерация локаций\n\nСейчас нет локаций на модерацию.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="moderation")]]),
        )
        return

    keyboard = [
        [InlineKeyboardButton(f"{loc.name} (#{loc.id})", callback_data=f"loc_detail_{loc.id}")]
        for loc in locations
    ]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="moderation")])
    await query.edit_message_text(
        "📍 Модерация локаций\nВыберите локацию:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


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
        return ConversationHandler.END

    if amount is None:
        try:
            amount = int(update.message.text.strip())
        except ValueError:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
            except Exception:
                pass
            menu_message_id = context.user_data.get("moderation_menu_message_id")
            if menu_message_id:
                await _safe_edit_menu_message(context, update.effective_user.id, menu_message_id, "Введите целое число:")
            return POINTS_CUSTOM

    with get_db_context() as db:
        new_value, label = _apply_points_change(db, data, amount)

    if new_value is None:
        return ConversationHandler.END

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass
    context.user_data["points_flash"] = f"✅ Новый баланс {label} баллов: {new_value}"
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
        return ConversationHandler.END

    context.user_data["points_flash"] = f"✅ Новый баланс {label} баллов: {new_value}"
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
    context.user_data.pop("delete_locations_active", None)
    await render_delete_locations(update, context)
    return DEL_SELECT


async def render_delete_locations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db_context() as db:
        locations = db.query(Location).filter(Location.status != "deleted").limit(20).all()

    flash = context.user_data.pop("delete_flash", None)
    if not locations:
        menu_message_id = context.user_data.get("moderation_menu_message_id")
        if menu_message_id:
            text_value = "Локаций нет."
            if flash:
                text_value = f"{flash}\n\n{text_value}"
            await context.bot.edit_message_text(
                text_value,
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
    text_value = "Выберите локацию:"
    if flash:
        text_value = f"{flash}\n\n{text_value}"
    if menu_message_id:
        await context.bot.edit_message_text(
            text_value,
            chat_id=update.effective_user.id,
            message_id=menu_message_id,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        target = update.message or (update.callback_query.message if update.callback_query else None)
        if target:
            sent = await target.reply_text(
                text_value,
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
    context.user_data["delete_flash"] = "✅ Локация удалена."
    await render_delete_locations(update, context)


async def delete_locations_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("delete_locations_active"):
        return
    context.user_data.pop("delete_locations_active", None)
    await update.message.reply_text("\u2060", reply_markup=ReplyKeyboardRemove())
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
    status = query.data.replace("tickets_", "")
    context.user_data["tickets_status"] = status
    await _render_tickets_list(update, context, status)
    return TICKETS_SELECT


async def tickets_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    term = update.message.text.strip()
    status = context.user_data.get("tickets_status", "new")
    with get_db_context() as db:
        query = db.query(SupportTicket, User).join(User, SupportTicket.user_id == User.id)
        status_map = {"new": SUPPORT_STATUS_NEW, "in_progress": SUPPORT_STATUS_IN_PROGRESS, "waiting_user": SUPPORT_STATUS_WAITING_USER, "closed": SUPPORT_STATUS_CLOSED, "active": None}
        if status == "active":
            query = query.filter(SupportTicket.status.in_(SUPPORT_ACTIVE_STATUSES))
        else:
            query = query.filter(SupportTicket.status == status_map.get(status, SUPPORT_STATUS_NEW))
        if term != "-":
            if term.isdigit():
                query = query.filter(SupportTicket.id == int(term))
            else:
                query = query.filter(User.username.ilike(f"%{term}%"))
        results = query.order_by(SupportTicket.created_at.desc()).limit(15).all()

    if not results:
        await update.message.reply_text("Тикеты не найдены. Попробуйте снова:")
        return TICKETS_SEARCH

    keyboard = []
    for ticket, user in results:
        label = f"#{ticket.id} · {user.username or user.first_name or user.id}"
        if ticket.unread_for_moderator:
            label += " 🔔"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"ticket_select_{status}_{ticket.id}")])
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
    payload = query.data.replace("ticket_select_", "")
    status, ticket_id_raw = payload.rsplit("_", 1)
    ticket_id = int(ticket_id_raw)

    with get_db_context() as db:
        set_active_ticket_id(db, update.effective_user.id, "moderator", ticket_id)
        set_session_mode(db, update.effective_user.id, "moderator", "idle")
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        user = db.query(User).filter(User.id == ticket.user_id).first() if ticket else None
        message_rows = (
            db.query(SupportMessage)
            .filter(SupportMessage.ticket_id == ticket_id)
            .order_by(SupportMessage.created_at.asc())
            .all()
        ) if ticket else []

        if not ticket:
            await query.edit_message_text("⚠️ Тикет не найден.")
            return ConversationHandler.END

        user_label = _build_user_label(
            user.username if user else None,
            user.first_name if user else None,
            ticket.user_id,
        )
        ticket_status = ticket.status
        messages = [_serialize_support_message(msg) for msg in message_rows]

        if ticket:
            ticket.unread_for_moderator = False
            if ticket.status == SUPPORT_STATUS_NEW:
                ticket.status = SUPPORT_STATUS_IN_PROGRESS
            db.commit()

    history_text = _format_ticket_history_payload(messages)

    rows = []
    if ticket_status != SUPPORT_STATUS_CLOSED:
        rows.append([InlineKeyboardButton("✍️ Ответить текстом", callback_data=f"mod_ticket_reply_text_{ticket_id}")])
        rows.append([InlineKeyboardButton("🖼 Отправить фото", callback_data=f"mod_ticket_reply_photo_{ticket_id}")])
        rows.append([InlineKeyboardButton("📄 Отправить документ", callback_data=f"mod_ticket_reply_document_{ticket_id}")])
        if ticket_status != SUPPORT_STATUS_IN_PROGRESS:
            rows.append([InlineKeyboardButton("🛠 В работу", callback_data=f"mod_ticket_status_in_progress_{ticket_id}")])
        if ticket_status != SUPPORT_STATUS_WAITING_USER:
            rows.append([InlineKeyboardButton("⏳ Ожидает пользователя", callback_data=f"mod_ticket_status_waiting_user_{ticket_id}")])

    for msg in [m for m in messages if m["message_type"] in {"photo", "document"} and m.get("file_id")][-5:]:
        icon = "🖼" if msg["message_type"] == "photo" else "📄"
        rows.append([InlineKeyboardButton(f"{icon} Вложение #{msg['id']}", callback_data=f"mod_attach_{msg['id']}")])

    if ticket_status != SUPPORT_STATUS_CLOSED:
        rows.append([InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"ticket_close_{status}_{ticket_id}")])

    rows.append([InlineKeyboardButton("◀️ Назад", callback_data=f"tickets_{status}")])

    await query.edit_message_text(
        f"💬 Тикет #{ticket_id} · {user_label}\n\n{history_text}",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return TICKETS_SELECT


async def moderation_ticket_start_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _ensure_admin(update):
        return

    payload = query.data.replace("mod_ticket_reply_", "")
    action, ticket_id_raw = payload.rsplit("_", 1)
    ticket_id = int(ticket_id_raw)
    mode = f"reply_{action}"

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket or ticket.status == SUPPORT_STATUS_CLOSED:
            await query.answer("Тикет недоступен для ответа.", show_alert=True)
            return
        set_active_ticket_id(db, update.effective_user.id, "moderator", ticket_id)
        set_session_mode(db, update.effective_user.id, "moderator", mode)

    hints = {
        "reply_text": "Отправь текстовый ответ пользователю.",
        "reply_photo": "Отправь фото (можно с подписью).",
        "reply_document": "Отправь документ (можно с подписью).",
    }
    await query.answer(hints.get(mode, "Отправь ответ пользователю."))


async def moderation_ticket_set_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _ensure_admin(update):
        return

    payload = query.data.replace("mod_ticket_status_", "")
    status_part, ticket_id_raw = payload.rsplit("_", 1)
    ticket_id = int(ticket_id_raw)
    new_status = SUPPORT_STATUS_WAITING_USER if status_part == "waiting_user" else SUPPORT_STATUS_IN_PROGRESS

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket or ticket.status == SUPPORT_STATUS_CLOSED:
            await query.answer("Тикет не найден или закрыт.", show_alert=True)
            return
        ticket.status = new_status
        db.commit()

    status_kind = context.user_data.get("tickets_status", "new")
    query.data = f"ticket_select_{status_kind}_{ticket_id}"
    await tickets_select(update, context)


async def close_ticket_by_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _ensure_admin(update):
        await query.answer("⛔ Только для модераторов.", show_alert=True)
        return

    payload = query.data.replace("ticket_select_", "")
    status, ticket_id_raw = payload.rsplit("_", 1)
    ticket_id = int(ticket_id_raw)

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket or ticket.status == SUPPORT_STATUS_CLOSED:
            await query.answer("⚠️ Тикет уже закрыт или не найден.", show_alert=True)
            await _render_tickets_list(update, context, "closed")
            return
        ticket.status = SUPPORT_STATUS_CLOSED
        ticket.closed_at = datetime.utcnow()
        ticket.closed_by = update.effective_user.id
        ticket.unread_for_moderator = False
        ticket.unread_for_user = False
        user_id = ticket.user_id
        set_active_ticket_id(db, update.effective_user.id, "moderator", None)
        set_session_mode(db, update.effective_user.id, "moderator", "idle")
        db.commit()

    await context.bot.send_message(
        chat_id=user_id,
        text=f"✅ Ваш тикет #{ticket_id} закрыт модератором и перемещен в архив.",
    )
    context.user_data["tickets_status"] = "closed"
    await _render_tickets_list(update, context, "closed")


async def moderation_ticket_attachment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _ensure_admin(update):
        return

    msg_id = int(query.data.split("_")[-1])
    with get_db_context() as db:
        msg = db.query(SupportMessage).filter(SupportMessage.id == msg_id).first()
    if not msg or not msg.file_id:
        return

    if msg.message_type == "photo":
        await context.bot.send_photo(chat_id=update.effective_user.id, photo=msg.file_id, caption=msg.message)
    elif msg.message_type == "document":
        await context.bot.send_document(chat_id=update.effective_user.id, document=msg.file_id, caption=msg.message)



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
        TICKETS_MENU: [CallbackQueryHandler(tickets_choose_section, pattern="^tickets_(new|in_progress|waiting_user|closed)$")],
        TICKETS_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, tickets_search)],
        TICKETS_SELECT: [CallbackQueryHandler(tickets_select, pattern=r"^ticket_select_(new|in_progress|waiting_user|closed|active)_\d+$")],
    },
    fallbacks=[CommandHandler("cancel", moderation_menu)],
    allow_reentry=True,
)

moderation_close_ticket_handler = CallbackQueryHandler(close_ticket_by_moderator, pattern=r"^ticket_close_(new|in_progress|waiting_user|closed|active)_\d+$")
moderation_ticket_reply_handler = CallbackQueryHandler(moderation_ticket_start_reply, pattern=r"^mod_ticket_reply_(text|photo|document)_\d+$")
moderation_ticket_status_handler = CallbackQueryHandler(moderation_ticket_set_status, pattern=r"^mod_ticket_status_(in_progress|waiting_user)_\d+$")
moderation_delete_back_handler = MessageHandler(filters.Regex("^◀️ Назад$"), delete_locations_back)
moderation_ticket_attachment_handler = CallbackQueryHandler(moderation_ticket_attachment, pattern=r"^mod_attach_\d+$")
