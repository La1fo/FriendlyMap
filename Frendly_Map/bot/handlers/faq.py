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
from bot.services.faq_service import FaqService
from bot.utils.common import is_moderator

LIST, ADD_QUESTION, ADD_ANSWER, DELETE_CONFIRM = range(4)


async def list_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_db_context() as db:
        items = FaqService.list_items(db)
        can_edit = is_moderator(db, user_id)

    if not items:
        text = "FAQ пока пуст."
        if can_edit:
            text += "\nНажмите кнопку ниже, чтобы добавить ответ."
        await update.message.reply_text(text, reply_markup=_list_keyboard([], can_edit))
        return LIST

    hint = "❓ FAQ: выбери вопрос"
    if can_edit:
        hint += "\nМодератор: для ответа на существующий вопрос отправьте его ID."
    await update.message.reply_text(hint, reply_markup=_list_keyboard(items, can_edit))
    return LIST


def _list_keyboard(items, can_edit: bool):
    buttons = [[InlineKeyboardButton(item.question[:60], callback_data=f"faq_{item.id}")] for item in items]
    if can_edit:
        buttons.append([InlineKeyboardButton("➕ Добавить ответ", callback_data="faq_add")])
    return InlineKeyboardMarkup(buttons)


async def handle_faq_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    with get_db_context() as db:
        can_edit = is_moderator(db, update.effective_user.id)

    if data == "faq_add":
        if not can_edit:
            await query.edit_message_text("⛔ Только для модераторов.")
            return ConversationHandler.END
        await query.edit_message_text("Введите вопрос (можно новый):")
        return ADD_QUESTION

    if data.startswith("faq_"):
        item_id = int(data.split("_")[-1])
        with get_db_context() as db:
            item = FaqService.get_item(db, item_id)
        if not item:
            await query.edit_message_text("Вопрос не найден.")
            return LIST
        text = f"<b>Вопрос:</b> {item.question}\n\n<b>Ответ:</b> {item.answer}"
        if can_edit:
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🗑 Удалить", callback_data=f"faq_delete_{item.id}")]]
            )
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            await query.edit_message_text(text, parse_mode="HTML")
        return LIST

    if data.startswith("faq_delete_"):
        if not can_edit:
            await query.edit_message_text("⛔ Только для модераторов.")
            return ConversationHandler.END
        item_id = int(data.split("_")[-1])
        context.user_data["faq_delete_id"] = item_id
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Да", callback_data="faq_delete_yes"),
                InlineKeyboardButton("❌ Нет", callback_data="faq_delete_no"),
            ]
        ])
        await query.edit_message_text("Удалить этот ответ?", reply_markup=kb)
        return DELETE_CONFIRM

    if data in {"faq_delete_yes", "faq_delete_no"}:
        return await handle_delete_confirm(update, context)

    return LIST


async def add_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text.strip()
    if not question:
        await update.message.reply_text("Вопрос не может быть пустым.")
        return ADD_QUESTION
    if question.isdigit():
        item_id = int(question)
        with get_db_context() as db:
            item = FaqService.get_item(db, item_id)
        if item:
            context.user_data["faq_item_id"] = item.id
            context.user_data["faq_question"] = item.question
            await update.message.reply_text(f"Введите новый ответ для вопроса: {item.question}")
            return ADD_ANSWER
    context.user_data["faq_question"] = question
    await update.message.reply_text("Введите ответ:")
    return ADD_ANSWER


async def add_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.message.text.strip()
    question = context.user_data.get("faq_question")
    item_id = context.user_data.get("faq_item_id")
    if not question or not answer:
        await update.message.reply_text("Нужно заполнить и вопрос, и ответ.")
        return ADD_ANSWER

    with get_db_context() as db:
        if not is_moderator(db, update.effective_user.id):
            await update.message.reply_text("⛔ Только для модераторов.")
            return ConversationHandler.END
        if item_id:
            item = FaqService.get_item(db, item_id)
            if item:
                FaqService.update_item(db, item, answer)
        else:
            FaqService.create_item(db, question, answer, update.effective_user.id)

    context.user_data.pop("faq_question", None)
    context.user_data.pop("faq_item_id", None)
    await update.message.reply_text("✅ Ответ добавлен.")
    return ConversationHandler.END


async def handle_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "faq_delete_no":
        await query.edit_message_text("Удаление отменено.")
        return ConversationHandler.END

    item_id = context.user_data.get("faq_delete_id")
    if not item_id:
        await query.edit_message_text("Не удалось определить запись.")
        return ConversationHandler.END

    with get_db_context() as db:
        if not is_moderator(db, update.effective_user.id):
            await query.edit_message_text("⛔ Только для модераторов.")
            return ConversationHandler.END
        item = FaqService.get_item(db, item_id)
        if not item:
            await query.edit_message_text("Запись не найдена.")
            return ConversationHandler.END
        FaqService.delete_item(db, item)

    context.user_data.pop("faq_delete_id", None)
    await query.edit_message_text("✅ Ответ удалён.")
    return ConversationHandler.END


faq_handler = ConversationHandler(
    entry_points=[
        CommandHandler("faq", list_faq),
        MessageHandler(filters.Regex("^(❓ FAQ|faq)$"), list_faq),
    ],
    states={
        LIST: [
            CallbackQueryHandler(handle_faq_callback, pattern=r"^faq_"),
        ],
        ADD_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_question)],
        ADD_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_answer)],
        DELETE_CONFIRM: [
            CallbackQueryHandler(handle_faq_callback, pattern=r"^faq_delete_(yes|no)$"),
        ],
    },
    fallbacks=[CommandHandler("cancel", list_faq)],
    per_message=True,
    allow_reentry=True,
)
