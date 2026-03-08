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
from bot.models.support_ticket import SupportMessage, SupportTicket
from bot.models.user import User
from bot.utils.rank import get_user_rank_display


def _profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎫 Тикеты", callback_data="profile_tickets")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])


def _ticket_actions_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["◀️ Назад", "✅ Закрыть тикет"]],
        resize_keyboard=True
    )


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
            .filter(SupportTicket.user_id == uid, SupportTicket.status == "open")
            .first()
        )
        archived_tickets = (
            db.query(SupportTicket)
            .filter(SupportTicket.user_id == uid, SupportTicket.status == "closed")
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
    context.user_data.pop("profile_ticket_status", None)
    await query.edit_message_text("🎫 Тикеты", reply_markup=keyboard)


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



async def _send_ticket_list_message(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    status: str,
    old_message_id: int | None = None,
) -> None:
    with get_db_context() as db:
        tickets = (
            db.query(SupportTicket)
            .filter(SupportTicket.user_id == user_id, SupportTicket.status == status)
            .order_by(SupportTicket.created_at.desc())
            .all()
        )

    if not tickets:
        text = "Нет активных тикетов." if status == "open" else "Архив пуст."
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="profile_tickets")]])
    else:
        keyboard = [
            [InlineKeyboardButton(f"#{ticket.id}", callback_data=f"profile_ticket_{ticket.id}")]
            for ticket in tickets
        ]
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="profile_tickets")])
        text = "Выберите тикет:"
        keyboard = InlineKeyboardMarkup(keyboard)

    sent = await context.bot.send_message(chat_id=user_id, text=text, reply_markup=keyboard)
    context.user_data["profile_menu_message_id"] = sent.message_id

    if old_message_id:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=old_message_id)
        except Exception:
            pass


async def profile_tickets_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["profile_menu_message_id"] = query.message.message_id
    status = "open" if query.data.endswith("active") else "closed"
    context.user_data["profile_ticket_status"] = status

    with get_db_context() as db:
        tickets = (
            db.query(SupportTicket)
            .filter(SupportTicket.user_id == update.effective_user.id, SupportTicket.status == status)
            .order_by(SupportTicket.created_at.desc())
            .all()
        )

    if not tickets:
        empty_text = "Нет активных тикетов." if status == "open" else "Архив пуст."
        await query.edit_message_text(
            empty_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="profile_tickets")]
            ])
        )
        return

    keyboard = [
        [InlineKeyboardButton(f"#{ticket.id}", callback_data=f"profile_ticket_{ticket.id}")]
        for ticket in tickets
    ]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="profile_tickets")])
    await query.edit_message_text(
        "Выберите тикет:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def profile_ticket_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split("_")[-1])

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket or ticket.user_id != update.effective_user.id:
            await query.edit_message_text("⚠️ Тикет не найден.")
            return
        messages = (
            db.query(SupportMessage)
            .filter(SupportMessage.ticket_id == ticket_id)
            .order_by(SupportMessage.created_at.asc())
            .all()
        )
        ticket.unread_for_user = False
        db.commit()

    context.user_data["support_ticket_id"] = ticket_id
    context.user_data["support_chat_active"] = ticket.status == "open"
    context.user_data["profile_ticket_view"] = True
    context.user_data["profile_menu_message_id"] = query.message.message_id

    history_text = _format_ticket_history(messages)
    title = f"💬 Тикет #{ticket_id}\nСтатус: {'открыт' if ticket.status == 'open' else 'закрыт'}\n\n"
    await query.edit_message_text(title + history_text)
    await query.message.reply_text("⁠", reply_markup=_ticket_actions_keyboard())


async def profile_ticket_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("profile_ticket_view"):
        return

    status = context.user_data.get("profile_ticket_status", "open")
    old_menu_message_id = context.user_data.get("profile_menu_message_id")
    context.user_data.pop("support_chat_active", None)
    context.user_data.pop("profile_ticket_view", None)

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="⁠",
        reply_markup=ReplyKeyboardRemove(),
    )
    await _send_ticket_list_message(context, update.effective_user.id, status, old_menu_message_id)



async def profile_ticket_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("profile_ticket_view"):
        return

    ticket_id = context.user_data.get("support_ticket_id")
    if not ticket_id:
        await update.message.reply_text("⚠️ Тикет не выбран.", reply_markup=ReplyKeyboardRemove())
        return

    with get_db_context() as db:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket or ticket.user_id != update.effective_user.id:
            await update.message.reply_text("⚠️ Тикет не найден.", reply_markup=ReplyKeyboardRemove())
            return
        if ticket.status != "open":
            await update.message.reply_text("Тикет уже закрыт.", reply_markup=ReplyKeyboardRemove())
            return

        ticket.status = "closed"
        ticket.closed_at = datetime.utcnow()
        ticket.closed_by = update.effective_user.id
        db.commit()

    context.user_data["support_chat_active"] = False
    context.user_data.pop("support_ticket_id", None)
    context.user_data.pop("profile_ticket_view", None)

    old_menu_message_id = context.user_data.get("profile_menu_message_id")

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="⁠",
        reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data["profile_ticket_status"] = "open"
    await _send_ticket_list_message(context, update.effective_user.id, "open", old_menu_message_id)



profile_handler = CommandHandler("profile", profile)
profile_menu_handler = MessageHandler(filters.Regex("^(👤 Профиль|profile)$"), profile)
profile_callback_handler = CallbackQueryHandler(profile, pattern="^profile$")
profile_tickets_menu_handler = CallbackQueryHandler(profile_tickets_menu, pattern="^profile_tickets$")
profile_tickets_list_handler = CallbackQueryHandler(
    profile_tickets_list,
    pattern="^profile_tickets_(active|archive)$"
)
profile_ticket_chat_handler = CallbackQueryHandler(profile_ticket_chat, pattern="^profile_ticket_\\d+$")
profile_ticket_back_handler = MessageHandler(filters.Regex("^◀️ Назад$"), profile_ticket_back)
profile_ticket_close_handler = MessageHandler(filters.Regex("^✅ Закрыть тикет$"), profile_ticket_close)
