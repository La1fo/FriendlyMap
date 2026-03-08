from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import get_db_context
from bot.models.support_ticket import SupportMessage, SupportTicket
from bot.services.support_state import get_active_ticket_id, set_active_ticket_id
from bot.utils.common import is_admin

SUPPORT_BACK_TEXT = "◀️ Назад"
SUPPORT_CLOSE_TEXT = "✅ Закрыть тикет"


def _support_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Открыть тикет", callback_data="support_open")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])


def _support_chat_reply_keyboard(ticket_open: bool = True) -> ReplyKeyboardMarkup:
    if ticket_open:
        return ReplyKeyboardMarkup([[SUPPORT_BACK_TEXT, SUPPORT_CLOSE_TEXT]], resize_keyboard=True)
    return ReplyKeyboardMarkup([[SUPPORT_BACK_TEXT]], resize_keyboard=True)


def _support_chat_text(ticket: SupportTicket) -> str:
    title = ticket.subject or "без названия"
    status = "открыт" if ticket.status == "open" else "закрыт"
    return f"💬 Тикет #{ticket.id} · {title}\nСтатус: {status}\nНапиши сообщение в поддержку."


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


async def _show_support_reply_keyboard(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    ticket_open: bool,
) -> None:
    await context.bot.send_message(chat_id=user_id, text="\u2060", reply_markup=_support_chat_reply_keyboard(ticket_open))


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


async def _deliver_support_message_to_user(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    ticket_id: int,
    payload: dict,
) -> None:
    prefix = f"👮 Ответ модератора по тикету #{ticket_id}:"
    if payload["message_type"] == "photo" and payload["file_id"]:
        await context.bot.send_photo(
            chat_id=user_id,
            photo=payload["file_id"],
            caption=f"{prefix}\n{payload['message']}",
        )
        return
    if payload["message_type"] == "document" and payload["file_id"]:
        await context.bot.send_document(
            chat_id=user_id,
            document=payload["file_id"],
            caption=f"{prefix}\n{payload['message']}",
        )
        return
    await context.bot.send_message(chat_id=user_id, text=f"{prefix}\n{payload['message']}")


async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        context.user_data["support_menu_message_id"] = update.callback_query.message.message_id

    await _edit_support_menu_message(
        context,
        update.effective_user.id,
        "🆘 Поддержка",
        reply_markup=_support_menu_keyboard(),
    )


async def open_support_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    with get_db_context() as db:
        ticket = (
            db.query(SupportTicket)
            .filter(SupportTicket.user_id == user_id, SupportTicket.status == "open")
            .order_by(SupportTicket.created_at.desc())
            .first()
        )
        if not ticket:
            ticket = SupportTicket(
                user_id=user_id,
                status="open",
                awaiting_subject=True,
                unread_for_moderator=True,
                unread_for_user=False,
            )
            db.add(ticket)
            db.commit()
            db.refresh(ticket)

        set_active_ticket_id(db, user_id, "user", ticket.id)

        if ticket.awaiting_subject or not ticket.subject:
            await _edit_support_menu_message(
                context,
                user_id,
                f"🆘 Тикет #{ticket.id} открыт. Введи название тикета одним сообщением.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="support")]]),
            )
            await _show_support_reply_keyboard(context, user_id, True)
            return

    await _edit_support_menu_message(
        context,
        user_id,
        _support_chat_text(ticket),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="support")]]),
    )
    await _show_support_reply_keyboard(context, user_id, ticket.status == "open")


async def support_reply_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db_context() as db:
        active_ticket_id = get_active_ticket_id(db, update.effective_user.id, "user")
        if not active_ticket_id:
            return
        set_active_ticket_id(db, update.effective_user.id, "user", None)

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass

    await context.bot.send_message(chat_id=update.effective_user.id, text="\u2060", reply_markup=ReplyKeyboardRemove())
    await _edit_support_menu_message(context, update.effective_user.id, "🆘 Поддержка", reply_markup=_support_menu_keyboard())


async def support_reply_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db_context() as db:
        ticket_id = get_active_ticket_id(db, update.effective_user.id, "user")
        if not ticket_id:
            return

        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id, SupportTicket.user_id == update.effective_user.id).first()
        if ticket and ticket.status == "open":
            ticket.status = "closed"
            ticket.closed_at = datetime.utcnow()
            ticket.closed_by = update.effective_user.id
            ticket.unread_for_moderator = False
            ticket.unread_for_user = False
            db.commit()

        set_active_ticket_id(db, update.effective_user.id, "user", None)

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass

    await context.bot.send_message(chat_id=update.effective_user.id, text="\u2060", reply_markup=ReplyKeyboardRemove())
    await _edit_support_menu_message(
        context,
        update.effective_user.id,
        "✅ Тикет закрыт. Он доступен в архиве профиля.",
        reply_markup=_support_menu_keyboard(),
    )


async def support_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    payload = _extract_support_payload(update.message)
    if not payload:
        return

    user_id = update.effective_user.id

    with get_db_context() as db:
        ticket_id = get_active_ticket_id(db, user_id, "user")
        if not ticket_id:
            return

        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id, SupportTicket.user_id == user_id).first()
        if not ticket or ticket.status != "open":
            set_active_ticket_id(db, user_id, "user", None)
            return

        if ticket.awaiting_subject:
            if payload["message_type"] != "text":
                return
            ticket.subject = payload["message"]
            ticket.awaiting_subject = False
            ticket.unread_for_moderator = True
            db.commit()
        else:
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
            db.commit()

        subject = ticket.subject

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass

    await _edit_support_menu_message(
        context,
        user_id,
        f"💬 Тикет #{ticket_id} · {subject or 'без названия'}\nНапиши сообщение в поддержку.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="support")]]),
    )


async def moderator_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id) or not update.message:
        return

    payload = _extract_support_payload(update.message)
    if not payload:
        return

    moderator_id = update.effective_user.id

    with get_db_context() as db:
        ticket_id = get_active_ticket_id(db, moderator_id, "moderator")
        if not ticket_id:
            return

        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket or ticket.status != "open":
            set_active_ticket_id(db, moderator_id, "moderator", None)
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
        db.commit()
        user_id = ticket.user_id

    await _deliver_support_message_to_user(context, user_id, ticket_id, payload)

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass


support_handler = CommandHandler("support", support_menu)
support_callback_handler = CallbackQueryHandler(support_menu, pattern="^support$")
support_open_handler = CallbackQueryHandler(open_support_ticket, pattern="^support_open$")

support_message_router = MessageHandler(
    (filters.TEXT | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND,
    support_message_handler,
    block=False,
)

support_reply_back_handler = MessageHandler(filters.Regex(f"^{SUPPORT_BACK_TEXT}$"), support_reply_back)
support_reply_close_handler = MessageHandler(filters.Regex(f"^{SUPPORT_CLOSE_TEXT}$"), support_reply_close)

moderator_message_router = MessageHandler(
    (filters.TEXT | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND,
    moderator_message_handler,
    block=False,
)
