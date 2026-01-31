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
from bot.services.faq_service import FaqService
from bot.utils.common import is_moderator

ASK_QUESTION, ASK_ANSWER = range(2)


async def show_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db_context() as db:
        items = FaqService.list_items(db)
        is_mod = is_moderator(db, update.effective_user.id)

    if not items:
        text = "FAQ пока пуст."
    else:
        text = "❓ FAQ: выберите вопрос"

    buttons = []
    for item in items:
        buttons.append([InlineKeyboardButton(item.question, callback_data=f"faq_view_{item.id}")])
    if is_mod:
        buttons.append([InlineKeyboardButton("➕ Добавить ответ", callback_data="faq_add")])
    buttons.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")])
    if buttons:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text)


async def faq_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "faq_add":
        with get_db_context() as db:
            if not is_moderator(db, update.effective_user.id):
                await query.edit_message_text("⛔ Доступ запрещен.")
                return ConversationHandler.END
        await query.edit_message_text("Введите вопрос:")
        return ASK_QUESTION

    if data.startswith("faq_view_"):
        item_id = int(data.split("_")[-1])
        with get_db_context() as db:
            item = FaqService.get_item(db, item_id)
            is_mod = is_moderator(db, update.effective_user.id)
        if not item:
            await query.edit_message_text("Вопрос не найден.")
            return ConversationHandler.END
        buttons = []
        if is_mod:
            buttons.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"faq_delete_{item.id}")])
        buttons.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")])
        await query.edit_message_text(
            f"<b>{item.question}</b>\n\n{item.answer}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
        )
        return ConversationHandler.END

    if data.startswith("faq_delete_"):
        item_id = int(data.split("_")[-1])
        with get_db_context() as db:
            if not is_moderator(db, update.effective_user.id):
                await query.edit_message_text("⛔ Доступ запрещен.")
                return ConversationHandler.END
        context.user_data["faq_delete_id"] = item_id
        await query.edit_message_text("Подтвердите удаление: ответьте 'да' или 'нет'.")
        return ASK_ANSWER

    return ConversationHandler.END


async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text.strip()
    if len(question) < 3:
        await update.message.reply_text("Вопрос слишком короткий. Попробуйте снова:")
        return ASK_QUESTION
    context.user_data["faq_question"] = question
    await update.message.reply_text("Введите ответ:")
    return ASK_ANSWER


async def ask_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    delete_id = context.user_data.get("faq_delete_id")
    if delete_id:
        if text.lower() != "да":
            await update.message.reply_text("Удаление отменено.")
            context.user_data.pop("faq_delete_id", None)
            return ConversationHandler.END
        with get_db_context() as db:
            if not is_moderator(db, update.effective_user.id):
                await update.message.reply_text("⛔ Доступ запрещен.")
                return ConversationHandler.END
            item = FaqService.get_item(db, delete_id)
            if not item:
                await update.message.reply_text("Вопрос не найден.")
                return ConversationHandler.END
            FaqService.delete_item(db, item)
        context.user_data.pop("faq_delete_id", None)
        await update.message.reply_text("Вопрос удален.")
        return ConversationHandler.END

    question = context.user_data.get("faq_question")
    if not question:
        await update.message.reply_text("Не удалось определить вопрос.")
        return ConversationHandler.END
    if len(text) < 3:
        await update.message.reply_text("Ответ слишком короткий. Попробуйте снова:")
        return ASK_ANSWER

    with get_db_context() as db:
        if not is_moderator(db, update.effective_user.id):
            await update.message.reply_text("⛔ Доступ запрещен.")
            return ConversationHandler.END
        FaqService.create_item(db, question, text, update.effective_user.id)

    context.user_data.pop("faq_question", None)
    await update.message.reply_text("✅ Ответ добавлен в FAQ.")
    return ConversationHandler.END


faq_menu_handler = CommandHandler("faq", show_faq)
faq_menu_button_handler = MessageHandler(filters.Regex("^(❓ FAQ|faq)$"), show_faq)

faq_conversation_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(faq_callback, pattern=r"^faq_(view|add|delete)_?\d*$"),
    ],
    states={
        ASK_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_question)],
        ASK_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_answer)],
    },
    fallbacks=[],
    per_message=True,
)
