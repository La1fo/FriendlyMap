from datetime import datetime
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.database import get_db_context
from bot.models.support_ticket import SupportTicket, SupportMessage
from bot.utils.common import is_admin

SUPPORT_OPEN_TEXT = "🟢 Открыть тикет"
SUPPORT_BACK_TEXT = "◀️ Назад"
SUPPORT_CLOSE_TEXT = "✅ Закрыть тикет"


def _get_mod_unread(context: ContextTypes.DEFAULT_TYPE) -> set[int]:
    return context.bot_data.setdefault("mod_unread_tickets", set())


def _support_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Открыть тикет", callback_data="support_open")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])


def _support_chat_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[SUPPORT_BACK_TEXT, SUPPORT_CLOSE_TEXT]], resize_keyboard=True)


def _support_chat_text(ticket_id: int, subject: str | None = None) -> str:
    title = subject or "без названия"
    return f"💬 Тикет #{ticket_id} · {title}\nНапиши сообщение в поддержку."


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

async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        context.user_data["support_menu_message_id"] = update.callback_query.message.message_id

    context.user_data.pop("awaiting_support_subject", None)
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
            .first()
        )
        if not ticket:
            ticket = SupportTicket(user_id=user_id, status="open")
            db.add(ticket)
            db.commit()
            db.refresh(ticket)

    context.user_data["support_ticket_id"] = ticket.id
    context.user_data["support_chat_active"] = False
    context.user_data["awaiting_support_subject"] = True

    _get_mod_unread(context).add(ticket.id)

    await _edit_support_menu_message(
        context,
        user_id,
        f"🆘 Тикет #{ticket.id} открыт. Введи название тикета одним сообщением.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="support")]]),
    )
    await context.bot.send_message(chat_id=user_id, text="⁠", reply_markup=_support_chat_reply_keyboard())


async def support_reply_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("support_chat_active"):
        return
    context.user_data.pop("support_chat_active", None)
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass
    menu_message_id = context.user_data.get("support_menu_message_id")
    if menu_message_id:
        await context.bot.edit_message_text(
            "🆘 Поддержка",
            chat_id=update.effective_user.id,
            message_id=menu_message_id,
            reply_markup=_support_menu_keyboard()
        )
    await update.message.reply_text("\u2060", reply_markup=ReplyKeyboardRemove())


async def support_reply_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("support_chat_active"):
        return
    ticket_id = context.user_data.get("support_ticket_id")
    if not ticket_id:
        return
    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if ticket and ticket.status == "open":
            ticket.status = "closed"
            ticket.closed_at = datetime.utcnow()
            ticket.closed_by = update.effective_user.id
            db.commit()
    context.user_data.pop("support_chat_active", None)
    context.user_data.pop("support_ticket_id", None)
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass
    await update.message.reply_text("\u2060", reply_markup=ReplyKeyboardRemove())
    menu_message_id = context.user_data.get("support_menu_message_id")
    if menu_message_id:
        await context.bot.edit_message_text(
            "🆘 Поддержка",
            chat_id=update.effective_user.id,
            message_id=menu_message_id,
            reply_markup=_support_menu_keyboard()
        )


async def close_support_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split("_")[-1])

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket or ticket.status != "open":
            await query.edit_message_text("⚠️ Тикет уже закрыт или не найден.")
            return
        if ticket.user_id != update.effective_user.id and not is_admin(update.effective_user.id):
            await query.edit_message_text("⛔ Нет доступа.")
            return
        ticket.status = "closed"
        ticket.closed_at = datetime.utcnow()
        ticket.closed_by = update.effective_user.id
        db.commit()

    context.user_data.pop("support_ticket_id", None)
    context.user_data.pop("support_chat_active", None)
    await _edit_support_menu_message(context, update.effective_user.id, "✅ Тикет закрыт. Он доступен в архиве профиля.", reply_markup=_support_menu_keyboard())


async def support_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticket_id = context.user_data.get("support_ticket_id")
    if not ticket_id:
        return

    message_text = update.message.text.strip()
    if not message_text:
        return

    user_id = update.effective_user.id

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket or ticket.status != "open" or ticket.user_id != user_id:
            context.user_data.pop("support_ticket_id", None)
            return

        if context.user_data.get("awaiting_support_subject"):
            ticket.subject = message_text
            db.commit()
            context.user_data["awaiting_support_subject"] = False
            context.user_data["support_chat_active"] = True
        elif context.user_data.get("support_chat_active"):
            msg = SupportMessage(
                ticket_id=ticket_id,
                sender_id=user_id,
                sender_role="user",
                message=message_text
            )
            db.add(msg)
            db.commit()
        else:
            return

        subject = ticket.subject

    _get_mod_unread(context).add(ticket_id)
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass

    await _edit_support_menu_message(
        context,
        user_id,
        _support_chat_text(ticket_id, subject),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="support")]]),
    )


async def moderator_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    ticket_id = context.user_data.get("moderation_ticket_id")
    if not ticket_id:
        return

    message_text = update.message.text.strip()
    if not message_text:
        return

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket or ticket.status != "open":
            await update.message.reply_text("⚠️ Тикет закрыт или не найден.")
            context.user_data.pop("moderation_ticket_id", None)
            return

        msg = SupportMessage(
            ticket_id=ticket_id,
            sender_id=update.effective_user.id,
            sender_role="moderator",
            message=message_text
        )
        db.add(msg)
        db.commit()
        user_id = ticket.user_id

    await context.bot.send_message(
        chat_id=user_id,
        text=(
            f"👮 Ответ модератора по тикету #{ticket_id}:\n"
            f"{message_text}"
        ),
    )
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass


support_handler = CommandHandler("support", support_menu)

support_callback_handler = CallbackQueryHandler(support_menu, pattern="^support$")
support_open_handler = CallbackQueryHandler(open_support_ticket, pattern="^support_open$")


support_close_handler = CallbackQueryHandler(close_support_ticket, pattern="^support_close_\d+$")

support_message_router = MessageHandler(filters.TEXT & ~filters.COMMAND, support_message_handler)

support_reply_back_handler = MessageHandler(filters.Regex(f"^{SUPPORT_BACK_TEXT}$"), support_reply_back)
support_reply_close_handler = MessageHandler(filters.Regex(f"^{SUPPORT_CLOSE_TEXT}$"), support_reply_close)

moderator_message_router = MessageHandler(filters.TEXT & ~filters.COMMAND, moderator_message_handler)
