from html import escape
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.database import get_db_context
from bot.models.faq_entry import FaqEntry
from bot.utils.common import is_admin
from bot.utils.section_banners import get_section_banner, send_section_banner

ASK_QUESTION, ASK_ANSWER, EDIT_QUESTION, EDIT_ANSWER = range(4)


def _faq_keyboard(user_id: int) -> Optional[InlineKeyboardMarkup]:
    if not is_admin(user_id):
        return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]])
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Добавить вопрос", callback_data="faq_add"),
            InlineKeyboardButton("✏️ Редактировать", callback_data="faq_edit"),
        ],
        [InlineKeyboardButton("🗑 Удалить", callback_data="faq_delete")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])


def _render_faq_text(entries: list[FaqEntry]) -> str:
    lines = ["❓ <b>FAQ</b>"]
    for idx, entry in enumerate(entries, start=1):
        lines.append(f"\n<b>{idx}. {escape(entry.question)}</b>\n{escape(entry.answer)}")
    return "\n".join(lines)


async def show_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    with get_db_context() as db:
        entries = db.query(FaqEntry).order_by(FaqEntry.id.asc()).all()

    banner = get_section_banner("faq")
    banner_caption = f"<b>{banner['title']}</b>\n{banner['description']}"
    await send_section_banner(
        update,
        context,
        "faq",
        banner_caption,
        delete_origin=True,
    )

    text = _render_faq_text(entries) if entries else "❓ Пока нет вопросов в FAQ."
    sent = await context.bot.send_message(
        chat_id=user_id,
        text=text,
        parse_mode="HTML" if entries else None,
        reply_markup=_faq_keyboard(user_id),
    )
    context.user_data["faq_menu_message_id"] = sent.message_id


async def start_add_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()

    if not is_admin(update.effective_user.id):
        await chat.reply_text("⛔ Только для модераторов.")
        return ConversationHandler.END

    await chat.reply_text("Введите вопрос для FAQ:")
    return ASK_QUESTION


async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["faq_question"] = update.message.text.strip()
    await update.message.reply_text("Теперь введите ответ:")
    return ASK_ANSWER


async def save_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = context.user_data.get("faq_question")
    answer = update.message.text.strip()

    with get_db_context() as db:
        db.add(FaqEntry(question=question, answer=answer, created_by=update.effective_user.id))
        db.commit()

    context.user_data.pop("faq_question", None)
    await update.message.reply_text("✅ Вопрос добавлен в FAQ.")
    await show_faq(update, context)
    return ConversationHandler.END


async def start_edit_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ Только для модераторов.")
        return

    with get_db_context() as db:
        entries = db.query(FaqEntry).order_by(FaqEntry.id.asc()).all()

    if not entries:
        await query.edit_message_text("❓ Пока нет вопросов в FAQ.", reply_markup=_faq_keyboard(update.effective_user.id))
        return

    keyboard = [
        [InlineKeyboardButton(f"{idx}. {entry.question}", callback_data=f"faq_edit_item_{entry.id}")]
        for idx, entry in enumerate(entries, start=1)
    ]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="faq")])
    await query.edit_message_text("Выберите вопрос для редактирования:", reply_markup=InlineKeyboardMarkup(keyboard))


async def choose_edit_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    entry_id = int(query.data.split("_")[-1])

    with get_db_context() as db:
        entry = db.query(FaqEntry).filter(FaqEntry.id == entry_id).first()

    if not entry:
        await query.edit_message_text("⚠️ Вопрос не найден.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Редактировать вопрос", callback_data=f"faq_edit_q_{entry_id}")],
        [InlineKeyboardButton("📝 Редактировать ответ", callback_data=f"faq_edit_a_{entry_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="faq_edit")],
    ])
    await query.edit_message_text(
        f"Выбран FAQ #{entry_id}\n\nТекущий вопрос:\n{entry.question}\n\nТекущий ответ:\n{entry.answer}",
        reply_markup=keyboard,
    )


async def start_edit_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["faq_edit_id"] = int(query.data.split("_")[-1])
    await query.message.reply_text("Введите новый текст вопроса:")
    return EDIT_QUESTION


async def start_edit_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["faq_edit_id"] = int(query.data.split("_")[-1])
    await query.message.reply_text("Введите новый текст ответа:")
    return EDIT_ANSWER


async def save_edit_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entry_id = context.user_data.get("faq_edit_id")
    if not entry_id:
        return ConversationHandler.END

    with get_db_context() as db:
        entry = db.query(FaqEntry).filter(FaqEntry.id == entry_id).first()
        if entry:
            entry.question = update.message.text.strip()
            db.commit()

    context.user_data.pop("faq_edit_id", None)
    await update.message.reply_text("✅ Вопрос обновлен.")
    await show_faq(update, context)
    return ConversationHandler.END


async def save_edit_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entry_id = context.user_data.get("faq_edit_id")
    if not entry_id:
        return ConversationHandler.END

    with get_db_context() as db:
        entry = db.query(FaqEntry).filter(FaqEntry.id == entry_id).first()
        if entry:
            entry.answer = update.message.text.strip()
            db.commit()

    context.user_data.pop("faq_edit_id", None)
    await update.message.reply_text("✅ Ответ обновлен.")
    await show_faq(update, context)
    return ConversationHandler.END


async def start_delete_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ Только для модераторов.")
        return

    with get_db_context() as db:
        entries = db.query(FaqEntry).order_by(FaqEntry.id.asc()).all()

    if not entries:
        await query.edit_message_text("❓ Пока нет вопросов в FAQ.", reply_markup=_faq_keyboard(update.effective_user.id))
        return

    keyboard = [
        [InlineKeyboardButton(f"{idx}. {entry.question}", callback_data=f"faq_delete_{entry.id}")]
        for idx, entry in enumerate(entries, start=1)
    ]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="faq")])
    await query.edit_message_text("Выберите вопрос для удаления:", reply_markup=InlineKeyboardMarkup(keyboard))


async def confirm_delete_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    entry_id = int(query.data.split("_")[-1])

    with get_db_context() as db:
        entry = db.query(FaqEntry).filter(FaqEntry.id == entry_id).first()
        if entry:
            db.delete(entry)
            db.commit()

    await show_faq(update, context)


async def cancel_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("faq_question", None)
    context.user_data.pop("faq_edit_id", None)
    await update.message.reply_text("❌ Действие отменено.")
    await show_faq(update, context)
    return ConversationHandler.END


faq_handler = CommandHandler("faq", show_faq)
faq_callback_handler = CallbackQueryHandler(show_faq, pattern="^faq$")

faq_add_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_add_faq, pattern="^faq_add$"),
        CommandHandler("faq_add", start_add_faq),
    ],
    states={
        ASK_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_question)],
        ASK_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_answer)],
    },
    fallbacks=[CommandHandler("cancel", cancel_faq)],
    allow_reentry=True,
)

faq_edit_start_handler = CallbackQueryHandler(start_edit_faq, pattern="^faq_edit$")
faq_edit_pick_handler = CallbackQueryHandler(choose_edit_target, pattern=r"^faq_edit_item_\d+$")

faq_edit_question_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_edit_question, pattern=r"^faq_edit_q_\d+$")],
    states={EDIT_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_edit_question)]},
    fallbacks=[CommandHandler("cancel", cancel_faq)],
    allow_reentry=True,
)

faq_edit_answer_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_edit_answer, pattern=r"^faq_edit_a_\d+$")],
    states={EDIT_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_edit_answer)]},
    fallbacks=[CommandHandler("cancel", cancel_faq)],
    allow_reentry=True,
)

faq_delete_handler = CallbackQueryHandler(start_delete_faq, pattern="^faq_delete$")
faq_delete_confirm_handler = CallbackQueryHandler(confirm_delete_faq, pattern=r"^faq_delete_\d+$")
