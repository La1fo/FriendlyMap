from datetime import datetime
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
from bot.models.support_ticket import SUPPORT_ACTIVE_STATUSES, SUPPORT_STATUS_CLOSED, SupportMessage, SupportTicket
from bot.models.user import User
from bot.services.support_state import set_active_ticket_id
from bot.utils.rank import get_user_rank_display


def _profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎫 Тикеты", callback_data="profile_tickets")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        context.user_data["profile_menu_message_id"] = query.message.message_id

    uid = update.effective_user.id
    with get_db_context() as db:
        user = db.query(User).filter(User.id == uid).first()
        active_ticket = (
            db.query(SupportTicket)
            .filter(SupportTicket.user_id == uid, SupportTicket.status.in_(SUPPORT_ACTIVE_STATUSES))
            .first()
        )
        archived_tickets = (
            db.query(SupportTicket)
            .filter(SupportTicket.user_id == uid, SupportTicket.status == SUPPORT_STATUS_CLOSED)
            .order_by(SupportTicket.closed_at.desc())
            .limit(5)
            .all()
        )

    if not user:
        if query:
            await query.edit_message_text("Ошибка: профиль не найден 😢")
        else:
            await update.message.reply_text("Ошибка: профиль не найден 😢")
        return

    msg = (
        f"👤 Твой профиль\n\n"
        f"🌐 Ник: @{user.username or 'Не указан'}\n"
        f"⭐ Баллы: {user.points}\n"
        f"🎯 Ранговые очки: {user.pts}\n"
        f"🏅 Ранг: {get_user_rank_display(user.points)}\n"
        f"📍 Одобрено локаций: {user.approved_locations}"
    )

    if active_ticket:
        msg += f"\n\n🟢 Активный тикет: #{active_ticket.id}"

    if archived_tickets:
        archive_lines = ["\n📦 Архив тикетов:"]
        for ticket in archived_tickets:
            closed_at = ticket.closed_at.strftime("%d.%m.%Y") if ticket.closed_at else "-"
            archive_lines.append(f"• #{ticket.id} закрыт {closed_at}")
        msg += "\n".join(archive_lines)

    if query:
        await query.edit_message_text(msg, reply_markup=_profile_keyboard())
    else:
        sent = await update.message.reply_text(msg, reply_markup=_profile_keyboard())
        context.user_data["profile_menu_message_id"] = sent.message_id


async def profile_tickets_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["profile_menu_message_id"] = query.message.message_id

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 Активные", callback_data="profile_tickets_active"),
            InlineKeyboardButton("📦 Архив", callback_data="profile_tickets_archive"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="profile")],
    ])
    await query.edit_message_text("🎫 Тикеты", reply_markup=keyboard)


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


def _format_ticket_history(messages: list[dict[str, Any]]) -> str:
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


def _ticket_view_keyboard(messages: list[dict[str, Any]], ticket_id: int, ticket_status: str, list_kind: str) -> InlineKeyboardMarkup:
    attachments = [m for m in messages if m["message_type"] in {"photo", "document"} and m.get("file_id")]
    rows: list[list[InlineKeyboardButton]] = []
    for msg in attachments[-5:]:
        icon = "🖼" if msg["message_type"] == "photo" else "📄"
        rows.append([InlineKeyboardButton(f"{icon} Вложение #{msg['id']}", callback_data=f"profile_attach_{msg['id']}")])

    if ticket_status in SUPPORT_ACTIVE_STATUSES:
        rows.append([InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"profile_ticket_close_{ticket_id}")])

    rows.append([InlineKeyboardButton("◀️ Назад", callback_data=f"profile_tickets_{list_kind}")])
    return InlineKeyboardMarkup(rows)


async def _render_profile_ticket_list(query, user_id: int, status: str):
    with get_db_context() as db:
        tickets = (
            db.query(SupportTicket)
            .filter(SupportTicket.user_id == user_id, SupportTicket.status.in_(SUPPORT_ACTIVE_STATUSES)) if status == "active" else db.query(SupportTicket).filter(SupportTicket.user_id == user_id, SupportTicket.status == SUPPORT_STATUS_CLOSED)
            .order_by(SupportTicket.created_at.desc())
            .all()
        )

    if not tickets:
        empty_text = "Нет активных тикетов." if status == "active" else "Архив пуст."
        await query.edit_message_text(
            empty_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="profile_tickets")]
            ]),
        )
        return

    kind = "active" if status == "active" else "archive"
    keyboard = [
        [InlineKeyboardButton(f"#{ticket.id}", callback_data=f"profile_ticket_{kind}_{ticket.id}")]
        for ticket in tickets
    ]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="profile_tickets")])
    await query.edit_message_text("Выберите тикет:", reply_markup=InlineKeyboardMarkup(keyboard))


async def profile_tickets_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["profile_menu_message_id"] = query.message.message_id
    status = "active" if query.data.endswith("active") else "closed"
    await _render_profile_ticket_list(query, update.effective_user.id, status)


async def profile_ticket_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, _, list_kind, ticket_id_raw = query.data.split("_")
    ticket_id = int(ticket_id_raw)

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket or ticket.user_id != update.effective_user.id:
            await query.edit_message_text("⚠️ Тикет не найден.")
            return

        message_rows = (
            db.query(SupportMessage)
            .filter(SupportMessage.ticket_id == ticket_id)
            .order_by(SupportMessage.created_at.asc())
            .all()
        )
        messages = [_serialize_support_message(msg) for msg in message_rows]
        ticket_status = ticket.status

        ticket.unread_for_user = False
        set_active_ticket_id(db, update.effective_user.id, "user", ticket.id if ticket_status in SUPPORT_ACTIVE_STATUSES else None)
        db.commit()

    history_text = _format_ticket_history(messages)
    title = f"💬 Тикет #{ticket_id}\nСтатус: {'открыт' if ticket_status in SUPPORT_ACTIVE_STATUSES else 'закрыт'}\n\n"
    await query.edit_message_text(
        title + history_text,
        reply_markup=_ticket_view_keyboard(messages, ticket_id, ticket_status, list_kind),
    )


async def profile_ticket_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split("_")[-1])

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id, SupportTicket.user_id == update.effective_user.id).first()
        if not ticket:
            await query.answer("⚠️ Тикет не найден.", show_alert=True)
            return
        if ticket.status == SUPPORT_STATUS_CLOSED:
            await query.answer("Тикет уже закрыт.", show_alert=True)
            await _render_profile_ticket_list(query, update.effective_user.id, "closed")
            return

        ticket.status = SUPPORT_STATUS_CLOSED
        ticket.closed_at = datetime.utcnow()
        ticket.closed_by = update.effective_user.id
        ticket.unread_for_user = False
        ticket.unread_for_moderator = False
        set_active_ticket_id(db, update.effective_user.id, "user", None)
        db.commit()

    await _render_profile_ticket_list(query, update.effective_user.id, "active")


async def profile_ticket_attachment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    msg_id = int(query.data.split("_")[-1])

    with get_db_context() as db:
        msg = db.query(SupportMessage).filter(SupportMessage.id == msg_id).first()
        ticket = db.query(SupportTicket).filter(SupportTicket.id == msg.ticket_id).first() if msg else None

    if not msg or not msg.file_id or not ticket or ticket.user_id != update.effective_user.id:
        return

    if msg.message_type == "photo":
        await context.bot.send_photo(chat_id=update.effective_user.id, photo=msg.file_id, caption=msg.message)
    elif msg.message_type == "document":
        await context.bot.send_document(chat_id=update.effective_user.id, document=msg.file_id, caption=msg.message)


profile_handler = CommandHandler("profile", profile)
profile_menu_handler = MessageHandler(filters.Regex("^(👤 Профиль|profile)$"), profile)
profile_callback_handler = CallbackQueryHandler(profile, pattern="^profile$")
profile_tickets_menu_handler = CallbackQueryHandler(profile_tickets_menu, pattern="^profile_tickets$")
profile_tickets_list_handler = CallbackQueryHandler(profile_tickets_list, pattern="^profile_tickets_(active|archive)$")
profile_ticket_chat_handler = CallbackQueryHandler(profile_ticket_chat, pattern="^profile_ticket_(active|archive)_\\d+$")
profile_ticket_close_handler = CallbackQueryHandler(profile_ticket_close, pattern="^profile_ticket_close_\\d+$")
profile_ticket_attachment_handler = CallbackQueryHandler(profile_ticket_attachment, pattern="^profile_attach_\\d+$")
