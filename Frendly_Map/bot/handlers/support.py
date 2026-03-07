from datetime import datetime
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.database import get_db_context
from bot.models.support_ticket import SupportTicket, SupportMessage
from typing import Optional

from bot.models.user import User
from bot.utils.common import is_admin

SUPPORT_OPEN_TEXT = "🟢 Открыть тикет"
SUPPORT_BACK_TEXT = "◀️ Назад"
SUPPORT_CLOSE_TEXT = "✅ Закрыть тикет"


def _get_mod_unread(context: ContextTypes.DEFAULT_TYPE) -> set[int]:
    return context.bot_data.setdefault("mod_unread_tickets", set())


def _build_support_chat_keyboard(ticket_id: int, is_admin_user: bool) -> InlineKeyboardMarkup:
    buttons = []
    if is_admin_user:
        buttons.append([InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"ticket_close_{ticket_id}")])
        buttons.append([InlineKeyboardButton("🔙 К тикетам", callback_data="mod_tickets")])
    else:
        buttons.append([InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"support_close_{ticket_id}")])
    return InlineKeyboardMarkup(buttons)


def _support_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Открыть тикет", callback_data="support_open")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])


def _support_chat_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[SUPPORT_BACK_TEXT, SUPPORT_CLOSE_TEXT]], resize_keyboard=True)


def _build_support_start_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Открыть чат", callback_data=f"support_chat_{ticket_id}")],
        [InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"support_close_{ticket_id}")],
    ])


def _format_user(user: Optional[User], user_id: int) -> str:
    if not user:
        return f"<code>{user_id}</code>"
    name = user.username or user.first_name or "Пользователь"
    return f"{name} (<code>{user_id}</code>)"


async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "🆘 Поддержка",
            reply_markup=_support_menu_keyboard()
        )
        context.user_data["support_menu_message_id"] = update.callback_query.message.message_id
    else:
        sent = await update.message.reply_text("🆘 Поддержка", reply_markup=_support_menu_keyboard())
        context.user_data["support_menu_message_id"] = sent.message_id


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
    context.user_data["support_chat_active"] = True

    _get_mod_unread(context).add(ticket.id)

    await query.edit_message_text(
        f"🆘 Тикет #{ticket.id} открыт. Напиши сообщение.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data="support")]
        ])
    )
    await query.message.reply_text("Чат поддержки:", reply_markup=_support_chat_reply_keyboard())


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

    _get_mod_unread(context).add(ticket_id)
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass
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


support_handler = CommandHandler("support", support_menu)

support_callback_handler = CallbackQueryHandler(support_menu, pattern="^support$")
support_open_handler = CallbackQueryHandler(open_support_ticket, pattern="^support_open$")

support_chat_handler = CallbackQueryHandler(open_support_chat, pattern="^support_chat_\\d+$")

support_close_handler = CallbackQueryHandler(close_support_ticket, pattern="^support_close_\d+$")

support_message_router = MessageHandler(filters.TEXT & ~filters.COMMAND, support_message_handler)

support_reply_back_handler = MessageHandler(filters.Regex(f"^{SUPPORT_BACK_TEXT}$"), support_reply_back)
support_reply_close_handler = MessageHandler(filters.Regex(f"^{SUPPORT_CLOSE_TEXT}$"), support_reply_close)

moderator_message_router = MessageHandler(filters.TEXT & ~filters.COMMAND, moderator_message_handler)
