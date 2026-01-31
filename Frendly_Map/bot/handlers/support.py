from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
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
from bot.handlers.start import build_main_menu

SUPPORT_CHAT = 0


def _ticket_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Завершить тикет", callback_data=f"ticket_close_{ticket_id}")],
            [InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")],
        ]
    )


async def open_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_db_context() as db:
        ticket = TicketService.get_or_create_open_ticket(db, user_id)
        messages = TicketService.list_messages(db, ticket.id)
    context.user_data["ticket_id"] = ticket.id
    if messages:
        history = "\n".join(
            f"{'🧑‍💬' if m.author_role == 'user' else '🛡'} {m.text}" for m in messages[-10:]
        )
        await update.message.reply_text(f"История тикета #{ticket.id}:\n{history}")
    await update.message.reply_text(
        f"🎫 Тикет #{ticket.id} открыт. Напишите сообщение, и мы ответим.",
        reply_markup=_ticket_keyboard(ticket.id),
    )
    return SUPPORT_CHAT


async def support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticket_id = context.user_data.get("ticket_id")
    if not ticket_id:
        await update.message.reply_text("Тикет не найден. Используйте кнопку Техподдержка.")
        return ConversationHandler.END

    with get_db_context() as db:
        ticket = db.get(Ticket, ticket_id)
        if not ticket or ticket.status != "open":
            await update.message.reply_text("Тикет закрыт или не найден.")
            return ConversationHandler.END
        TicketService.add_message(db, ticket_id, "user", update.effective_user.id, update.message.text)

    await update.message.reply_text("Сообщение отправлено.")
    return SUPPORT_CHAT


async def close_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split("_")[-1])

    with get_db_context() as db:
        ticket = db.get(Ticket, ticket_id)
        if not ticket or ticket.status != "open":
            await query.edit_message_text("Тикет уже закрыт.")
            return ConversationHandler.END
        TicketService.close_ticket(db, ticket)

    context.user_data.pop("ticket_id", None)
    await query.edit_message_text("✅ Тикет закрыт.")
    return ConversationHandler.END


async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Главное меню:")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Выберите действие:",
        reply_markup=build_main_menu(update.effective_user),
    )
    return ConversationHandler.END


support_handler = ConversationHandler(
    entry_points=[
        CommandHandler("support", open_support),
        MessageHandler(filters.Regex("^(🆘 Техподдержка|support)$"), open_support),
    ],
    states={
        SUPPORT_CHAT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, support_message),
            CallbackQueryHandler(close_ticket, pattern=r"^ticket_close_\d+$"),
            CallbackQueryHandler(back_to_main_menu, pattern=r"^main_menu$"),
        ],
    },
    fallbacks=[],
    per_message=True,
)
