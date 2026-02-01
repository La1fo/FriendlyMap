from typing import Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.database import get_db_context
from bot.models.faq_entry import FaqEntry
from bot.utils.common import is_admin

ASK_QUESTION, ASK_ANSWER = range(2)


def _faq_keyboard(user_id: int) -> Optional[InlineKeyboardMarkup]:
    if not is_admin(user_id):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]
        ])
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Добавить вопрос", callback_data="faq_add"),
            InlineKeyboardButton("🗑 Удалить", callback_data="faq_delete"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])


async def show_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        chat = update.callback_query.message
        user_id = update.effective_user.id
    else:
        chat = update.message
        user_id = update.effective_user.id

    with get_db_context() as db:
        entries = db.query(FaqEntry).order_by(FaqEntry.id.asc()).all()

    if not entries:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "❓ Пока нет вопросов в FAQ.",
                reply_markup=_faq_keyboard(user_id)
            )
        else:
            await chat.reply_text(
                "❓ Пока нет вопросов в FAQ.",
                reply_markup=_faq_keyboard(user_id)
            )
        return

    lines = ["❓ <b>FAQ</b>"]
    for idx, entry in enumerate(entries, start=1):
        lines.append(f"\n<b>{idx}. {entry.question}</b>\n{entry.answer}")

    if update.callback_query:
        await update.callback_query.edit_message_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=_faq_keyboard(user_id)
        )
    else:
        await chat.reply_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=_faq_keyboard(user_id)
        )


async def start_add_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        chat = update.callback_query.message
    else:
        chat = update.message

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
        entry = FaqEntry(
            question=question,
            answer=answer,
            created_by=update.effective_user.id
        )
        db.add(entry)
        db.commit()

    context.user_data.pop("faq_question", None)
    await update.message.reply_text("✅ Вопрос добавлен в FAQ.")
    await show_faq(update, context)
    return ConversationHandler.END


async def cancel_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("faq_question", None)
    await update.message.reply_text("❌ Добавление FAQ отменено.")
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
        await query.edit_message_text(
            "❓ Пока нет вопросов в FAQ.",
            reply_markup=_faq_keyboard(update.effective_user.id)
        )
        return

    keyboard = [
        [InlineKeyboardButton(f"{idx}. {entry.question}", callback_data=f"faq_delete_{entry.id}")]
        for idx, entry in enumerate(entries, start=1)
    ]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="faq")])
    await query.edit_message_text(
        "Выберите вопрос для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


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


faq_handler = CommandHandler("faq", show_faq)
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
faq_callback_handler = CallbackQueryHandler(show_faq, pattern="^faq$")
faq_delete_handler = CallbackQueryHandler(start_delete_faq, pattern="^faq_delete$")
faq_delete_confirm_handler = CallbackQueryHandler(confirm_delete_faq, pattern="^faq_delete_\\d+$")
