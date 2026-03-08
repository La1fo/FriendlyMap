from datetime import datetime
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
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
    get_active_ticket_id,
    get_session_mode,
    set_active_ticket_id,
    set_session_mode,
)
from bot.utils.common import is_admin


def _support_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Открыть/продолжить тикет", callback_data="support_open")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])


def _status_text(status: str) -> str:
    return {
        SUPPORT_STATUS_NEW: "Новый",
        SUPPORT_STATUS_IN_PROGRESS: "В работе",
        SUPPORT_STATUS_WAITING_USER: "Ожидает пользователя",
        SUPPORT_STATUS_CLOSED: "Закрыт",
    }.get(status, status)


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
    for msg in messages[-8:]:
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


async def _edit_support_menu_message(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    text_value: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    message_id = context.user_data.get("support_menu_message_id")
    if message_id:
        try:
            await context.bot.edit_message_text(
                text_value,
                chat_id=user_id,
                message_id=message_id,
                reply_markup=reply_markup,
            )
            return
        except BadRequest:
            pass

    sent = await context.bot.send_message(chat_id=user_id, text=text_value, reply_markup=reply_markup)
    context.user_data["support_menu_message_id"] = sent.message_id


def _user_ticket_keyboard(ticket: SupportTicket, messages: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    rows.append([InlineKeyboardButton("✍️ Ответить", callback_data=f"support_reply_{ticket.id}")])

    attachments = [m for m in messages if m["message_type"] in {"photo", "document"} and m.get("file_id")]
    for msg in attachments[-3:]:
        icon = "🖼" if msg["message_type"] == "photo" else "📄"
        rows.append([InlineKeyboardButton(f"{icon} Вложение #{msg['id']}", callback_data=f"support_attach_{msg['id']}")])

    if ticket.status != SUPPORT_STATUS_CLOSED:
        rows.append([InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"support_close_{ticket.id}")])
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="support")])
    return InlineKeyboardMarkup(rows)


async def _render_user_ticket_screen(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    ticket_id: int,
) -> None:
    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id, SupportTicket.user_id == user_id).first()
        if not ticket:
            await _edit_support_menu_message(context, user_id, "⚠️ Тикет не найден.", reply_markup=_support_menu_keyboard())
            return

        msg_rows = (
            db.query(SupportMessage)
            .filter(SupportMessage.ticket_id == ticket_id)
            .order_by(SupportMessage.created_at.asc())
            .all()
        )
        messages = [_serialize_support_message(msg) for msg in msg_rows]

        ticket.unread_for_user = False
        db.commit()

    title = ticket.subject or "без названия"
    text = (
        f"💬 Тикет #{ticket.id} · {title}\n"
        f"Статус: {_status_text(ticket.status)}\n\n"
        f"{_format_ticket_history(messages)}"
    )
    await _edit_support_menu_message(context, user_id, text, reply_markup=_user_ticket_keyboard(ticket, messages))


def _extract_support_payload(message: Message) -> dict | None:
    if message.text:
        return {
            "message_type": "text",
            "message": message.text.strip(),
            "file_id": None,
            "file_name": None,
            "mime_type": None,
        }
    if message.photo:
        return {
            "message_type": "photo",
            "message": (message.caption or "Фото"),
            "file_id": message.photo[-1].file_id,
            "file_name": None,
            "mime_type": None,
        }
    if message.document:
        return {
            "message_type": "document",
            "message": (message.caption or message.document.file_name or "Документ"),
            "file_id": message.document.file_id,
            "file_name": message.document.file_name,
            "mime_type": message.document.mime_type,
        }
    return None


async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        context.user_data["support_menu_message_id"] = update.callback_query.message.message_id

    await _edit_support_menu_message(
        context,
        update.effective_user.id,
        "🆘 Поддержка\nОткрой тикет и веди диалог в карточке тикета.",
        reply_markup=_support_menu_keyboard(),
    )


async def open_support_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    with get_db_context() as db:
        ticket = (
            db.query(SupportTicket)
            .filter(SupportTicket.user_id == user_id, SupportTicket.status.in_(SUPPORT_ACTIVE_STATUSES))
            .order_by(SupportTicket.created_at.desc())
            .first()
        )
        if not ticket:
            ticket = SupportTicket(
                user_id=user_id,
                status=SUPPORT_STATUS_NEW,
                awaiting_subject=True,
                unread_for_moderator=True,
                unread_for_user=False,
            )
            db.add(ticket)
            db.commit()
            db.refresh(ticket)

        set_active_ticket_id(db, user_id, "user", ticket.id)
        if ticket.awaiting_subject or not ticket.subject:
            set_session_mode(db, user_id, "user", "subject")
            await _edit_support_menu_message(
                context,
                user_id,
                f"🆘 Тикет #{ticket.id} создан. Напиши тему тикета одним сообщением.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="support")]]),
            )
            return

        set_session_mode(db, user_id, "user", "idle")

    await _render_user_ticket_screen(context, user_id, ticket.id)


async def support_start_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split("_")[-1])
    user_id = update.effective_user.id

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id, SupportTicket.user_id == user_id).first()
        if not ticket or ticket.status == SUPPORT_STATUS_CLOSED:
            await query.answer("Тикет недоступен для ответа.", show_alert=True)
            return
        set_active_ticket_id(db, user_id, "user", ticket.id)
        set_session_mode(db, user_id, "user", "reply")

    await query.answer("Отправь одно сообщение, фото или документ в ответ.")


async def support_close_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split("_")[-1])
    user_id = update.effective_user.id

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id, SupportTicket.user_id == user_id).first()
        if not ticket:
            await query.answer("⚠️ Тикет не найден.", show_alert=True)
            return
        if ticket.status == SUPPORT_STATUS_CLOSED:
            await query.answer("Тикет уже закрыт.", show_alert=True)
            set_active_ticket_id(db, user_id, "user", None)
            set_session_mode(db, user_id, "user", "idle")
            await _edit_support_menu_message(context, user_id, "✅ Тикет закрыт.", reply_markup=_support_menu_keyboard())
            return

        ticket.status = SUPPORT_STATUS_CLOSED
        ticket.closed_at = datetime.utcnow()
        ticket.closed_by = user_id
        ticket.unread_for_moderator = False
        ticket.unread_for_user = False
        db.commit()

        set_active_ticket_id(db, user_id, "user", None)
        set_session_mode(db, user_id, "user", "idle")

    await _edit_support_menu_message(context, user_id, "✅ Тикет закрыт. Он доступен в архиве профиля.", reply_markup=_support_menu_keyboard())


async def support_ticket_attachment(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def support_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    payload = _extract_support_payload(update.message)
    if not payload:
        return

    user_id = update.effective_user.id

    with get_db_context() as db:
        ticket_id = get_active_ticket_id(db, user_id, "user")
        mode = get_session_mode(db, user_id, "user")
        if not ticket_id or mode == "idle":
            return

        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id, SupportTicket.user_id == user_id).first()
        if not ticket or ticket.status == SUPPORT_STATUS_CLOSED:
            set_active_ticket_id(db, user_id, "user", None)
            set_session_mode(db, user_id, "user", "idle")
            return

        if mode == "subject":
            if payload["message_type"] != "text":
                return
            ticket.subject = payload["message"]
            ticket.awaiting_subject = False
            ticket.status = SUPPORT_STATUS_NEW
            ticket.unread_for_moderator = True
            ticket.unread_for_user = False
            db.commit()
            set_session_mode(db, user_id, "user", "idle")
            render_ticket_id = ticket.id
        elif mode == "reply":
            msg = SupportMessage(
                ticket_id=ticket.id,
                sender_id=user_id,
                sender_role="user",
                message_type=payload["message_type"],
                message=payload["message"],
                file_id=payload["file_id"],
                file_name=payload["file_name"],
                mime_type=payload["mime_type"],
            )
            db.add(msg)
            ticket.unread_for_moderator = True
            ticket.unread_for_user = False
            ticket.status = SUPPORT_STATUS_IN_PROGRESS
            db.commit()
            set_session_mode(db, user_id, "user", "idle")
            render_ticket_id = ticket.id
        else:
            return

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass

    await _render_user_ticket_screen(context, user_id, render_ticket_id)


async def _deliver_support_message_to_user(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    ticket_id: int,
    payload: dict,
) -> None:
    prefix = f"👮 Ответ модератора по тикету #{ticket_id}:"
    if payload["message_type"] == "photo" and payload["file_id"]:
        await context.bot.send_photo(chat_id=user_id, photo=payload["file_id"], caption=f"{prefix}\n{payload['message']}")
        return
    if payload["message_type"] == "document" and payload["file_id"]:
        await context.bot.send_document(chat_id=user_id, document=payload["file_id"], caption=f"{prefix}\n{payload['message']}")
        return
    await context.bot.send_message(chat_id=user_id, text=f"{prefix}\n{payload['message']}")


async def moderator_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id) or not update.message:
        return

    payload = _extract_support_payload(update.message)
    if not payload:
        return

    moderator_id = update.effective_user.id

    with get_db_context() as db:
        ticket_id = get_active_ticket_id(db, moderator_id, "moderator")
        mode = get_session_mode(db, moderator_id, "moderator")
        if not ticket_id or mode != "reply":
            return

        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket or ticket.status == SUPPORT_STATUS_CLOSED:
            set_active_ticket_id(db, moderator_id, "moderator", None)
            set_session_mode(db, moderator_id, "moderator", "idle")
            return

        msg = SupportMessage(
            ticket_id=ticket.id,
            sender_id=moderator_id,
            sender_role="moderator",
            message_type=payload["message_type"],
            message=payload["message"],
            file_id=payload["file_id"],
            file_name=payload["file_name"],
            mime_type=payload["mime_type"],
        )
        db.add(msg)
        ticket.unread_for_user = True
        ticket.unread_for_moderator = False
        ticket.status = SUPPORT_STATUS_WAITING_USER
        db.commit()
        user_id = ticket.user_id
        set_session_mode(db, moderator_id, "moderator", "idle")

    await _deliver_support_message_to_user(context, user_id, ticket_id, payload)

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass


support_handler = CommandHandler("support", support_menu)
support_callback_handler = CallbackQueryHandler(support_menu, pattern="^support$")
support_open_handler = CallbackQueryHandler(open_support_ticket, pattern="^support_open$")
support_start_reply_handler = CallbackQueryHandler(support_start_reply, pattern=r"^support_reply_\d+$")
support_close_callback_handler = CallbackQueryHandler(support_close_ticket, pattern=r"^support_close_\d+$")
support_attachment_handler = CallbackQueryHandler(support_ticket_attachment, pattern=r"^support_attach_\d+$")

support_message_router = MessageHandler(
    (filters.TEXT | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND,
    support_message_handler,
    block=False,
)

moderator_message_router = MessageHandler(
    (filters.TEXT | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND,
    moderator_message_handler,
    block=False,
)
