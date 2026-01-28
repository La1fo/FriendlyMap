from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.database import get_db_context
from bot.models.ticket import Ticket
from bot.services.ticket_service import TicketService
from bot.utils.common import is_moderator

CHAT = 0


def _close_keyboard(ticket_id: int):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Завершить тикет", callback_data=f"ticket_close_{ticket_id}")]]
    )


async def open_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_db_context() as db:
        ticket = TicketService.get_or_create_open_ticket(db, user_id)
        messages = TicketService.list_messages(db, ticket.id)

    context.user_data["ticket_id"] = ticket.id
    context.user_data["ticket_role"] = "user"

    history = _format_history(messages)
    text = (
        f"🆘 Техподдержка (тикет #{ticket.id})\n"
        f"Статус: {ticket.status}\n\n"
        f"{history}\n"
        "Напишите сообщение, чтобы продолжить диалог."
    )
    await update.message.reply_text(text, reply_markup=_close_keyboard(ticket.id))
    return CHAT


async def open_ticket_for_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split("_")[-1])

    with get_db_context() as db:
        if not is_moderator(db, update.effective_user.id):
            await query.edit_message_text("⛔ Только для модераторов.")
            return ConversationHandler.END
        ticket = db.get(Ticket, ticket_id)
        if not ticket:
            await query.edit_message_text("Тикет не найден.")
            return ConversationHandler.END
        messages = TicketService.list_messages(db, ticket.id)

    context.user_data["ticket_id"] = ticket.id
    context.user_data["ticket_role"] = "moderator"

    history = _format_history(messages)
    text = (
        f"🎫 Тикет #{ticket.id}\n"
        f"Статус: {ticket.status}\n\n"
        f"{history}\n"
        "Напишите сообщение, чтобы ответить."
    )
    await query.edit_message_text(text, reply_markup=_close_keyboard(ticket.id))
    return CHAT


async def open_ticket_for_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split("_")[-1])

    with get_db_context() as db:
        ticket = db.get(Ticket, ticket_id)
        if not ticket or ticket.user_id != update.effective_user.id:
            await query.edit_message_text("Тикет не найден.")
            return ConversationHandler.END
        messages = TicketService.list_messages(db, ticket.id)

    context.user_data["ticket_id"] = ticket.id
    context.user_data["ticket_role"] = "user"

    history = _format_history(messages)
    text = (
        f"🎫 Тикет #{ticket.id}\n"
        f"Статус: {ticket.status}\n\n"
        f"{history}\n"
        "Напишите сообщение, чтобы продолжить диалог."
    )
    await query.edit_message_text(text, reply_markup=_close_keyboard(ticket.id))
    return CHAT


async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticket_id = context.user_data.get("ticket_id")
    role = context.user_data.get("ticket_role")
    if not ticket_id or not role:
        return

    text = update.message.text.strip()
    if not text:
        return

    with get_db_context() as db:
        ticket = db.get(Ticket, ticket_id)
        if not ticket:
            await update.message.reply_text("Тикет не найден.")
            return
        if ticket.status != "open":
            await update.message.reply_text("Тикет закрыт. Новые сообщения недоступны.")
            return
        TicketService.add_message(db, ticket_id, role, update.effective_user.id, text)

    await update.message.reply_text("✅ Сообщение отправлено.", reply_markup=_close_keyboard(ticket_id))


async def close_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split("_")[-1])

    with get_db_context() as db:
        ticket = db.get(Ticket, ticket_id)
        if not ticket:
            await query.edit_message_text("Тикет не найден.")
            return ConversationHandler.END
        if ticket.status == "closed":
            await query.edit_message_text("Тикет уже закрыт.")
            return ConversationHandler.END
        TicketService.close_ticket(db, ticket)

    context.user_data.pop("ticket_id", None)
    context.user_data.pop("ticket_role", None)
    await query.edit_message_text("✅ Тикет закрыт.")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("ticket_id", None)
    context.user_data.pop("ticket_role", None)
    await update.message.reply_text("Диалог с поддержкой завершён.")
    return ConversationHandler.END


def _format_history(messages):
    if not messages:
        return "История пока пуста."
    lines = []
    for message in messages[-10:]:
        prefix = "👤" if message.author_role == "user" else "🛡"
        lines.append(f"{prefix} {message.text}")
    return "\n".join(lines)


support_handler = ConversationHandler(
    entry_points=[
        CommandHandler("support", open_support),
        MessageHandler(filters.Regex("^(🆘 Техподдержка|support)$"), open_support),
        CallbackQueryHandler(open_ticket_for_moderator, pattern=r"^ticket_open_\d+$"),
        CallbackQueryHandler(open_ticket_for_user, pattern=r"^ticket_view_\d+$"),
    ],
    states={
        CHAT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message),
            CallbackQueryHandler(close_ticket, pattern=r"^ticket_close_\d+$"),
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=True,
    allow_reentry=True,
)
