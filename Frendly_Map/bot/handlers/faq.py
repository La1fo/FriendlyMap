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
        return None
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить вопрос", callback_data="faq_add")]
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
        await chat.reply_text(
            "❓ Пока нет вопросов в FAQ.",
            reply_markup=_faq_keyboard(user_id)
        )
        return

    lines = ["❓ <b>FAQ</b>"]
    for idx, entry in enumerate(entries, start=1):
        lines.append(f"\n<b>{idx}. {entry.question}</b>\n{entry.answer}")

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
    return ConversationHandler.END


async def cancel_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("faq_question", None)
    await update.message.reply_text("❌ Добавление FAQ отменено.")
    return ConversationHandler.END


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
