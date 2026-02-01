from datetime import datetime
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.config import settings
from bot.database import get_db_context
from bot.models.support_ticket import SupportTicket, SupportMessage
from typing import Optional

from bot.models.user import User
from bot.utils.common import is_admin


def _build_support_chat_keyboard(ticket_id: int, is_admin_user: bool) -> InlineKeyboardMarkup:
    buttons = []
    if is_admin_user:
        buttons.append([InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"ticket_close_{ticket_id}")])
        buttons.append([InlineKeyboardButton("🔙 К тикетам", callback_data="mod_tickets")])
    else:
        buttons.append([InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"support_close_{ticket_id}")])
    return InlineKeyboardMarkup(buttons)


def _build_support_start_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Открыть чат", callback_data=f"support_chat_{ticket_id}")],
        [InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"support_close_{ticket_id}")],
    ])


async def _send_to_admins(context: ContextTypes.DEFAULT_TYPE, text: str):
    for admin_id in settings.ADMIN_IDS_LIST:
        await context.bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")


def _format_user(user: Optional[User], user_id: int) -> str:
    if not user:
        return f"<code>{user_id}</code>"
    name = user.username or user.first_name or "Пользователь"
    return f"{name} (<code>{user_id}</code>)"


async def start_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        chat = update.callback_query.message
    else:
        chat = update.message

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

        user = db.query(User).filter(User.id == user_id).first()

    context.user_data["support_ticket_id"] = ticket.id
    context.user_data["support_chat_active"] = True

    await chat.reply_text(
        "🆘 Тикет поддержки открыт!\n"
        "Напиши сообщение, и модератор ответит как сможет.",
        reply_markup=_build_support_start_keyboard(ticket.id)
    )

    admin_text = (
        "🆘 Новый тикет поддержки\n"
        f"Пользователь: {_format_user(user, user_id)}\n"
        f"Тикет: #{ticket.id}"
    )
    await _send_to_admins(context, admin_text)


async def open_support_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split("_")[-1])

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()

    if not ticket or ticket.status != "open":
        await query.edit_message_text("⚠️ Тикет не найден или уже закрыт.")
        return

    if ticket.user_id != update.effective_user.id:
        await query.edit_message_text("⛔ Это не твой тикет.")
        return

    context.user_data["support_ticket_id"] = ticket_id
    context.user_data["support_chat_active"] = True
    await query.message.reply_text(
        f"💬 Чат тикета #{ticket_id} открыт. Пиши сообщение!",
        reply_markup=_build_support_chat_keyboard(ticket_id, False)
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
    await query.message.reply_text("✅ Тикет закрыт. Он доступен в архиве профиля.")


async def support_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticket_id = context.user_data.get("support_ticket_id")
    if not ticket_id or not context.user_data.get("support_chat_active"):
        return

    message_text = update.message.text.strip()
    if not message_text:
        return

    user_id = update.effective_user.id

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket or ticket.status != "open":
            await update.message.reply_text("⚠️ Тикет закрыт или не найден.")
            context.user_data.pop("support_ticket_id", None)
            return
        if ticket.user_id != user_id:
            return
        msg = SupportMessage(
            ticket_id=ticket_id,
            sender_id=user_id,
            sender_role="user",
            message=message_text
        )
        db.add(msg)
        db.commit()
        user = db.query(User).filter(User.id == user_id).first()

    admin_text = (
        f"💬 Сообщение по тикету #{ticket_id}\n"
        f"Пользователь: {_format_user(user, user_id)}\n\n"
        f"{escape(message_text)}"
    )
    await _send_to_admins(context, admin_text)
    await update.message.reply_text("✅ Сообщение отправлено в поддержку.")


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
    await update.message.reply_text("✅ Ответ отправлен пользователю.")


support_handler = CommandHandler("support", start_support)

support_callback_handler = CallbackQueryHandler(start_support, pattern="^support$")

support_chat_handler = CallbackQueryHandler(open_support_chat, pattern="^support_chat_\d+$")

support_close_handler = CallbackQueryHandler(close_support_ticket, pattern="^support_close_\d+$")

support_message_router = MessageHandler(filters.TEXT & ~filters.COMMAND, support_message_handler)

moderator_message_router = MessageHandler(filters.TEXT & ~filters.COMMAND, moderator_message_handler)
