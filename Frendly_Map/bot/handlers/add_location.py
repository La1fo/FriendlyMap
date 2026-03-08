from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.database import get_db_context
from bot.keyboards.main_menu import get_main_menu
from bot.services.achievements_manager import AchievementsManager
from bot.services.location_service import LocationService
from bot.utils.users import get_or_create_user

ASK_NAME, ASK_DESCRIPTION, ASK_LOCATION, ASK_PHOTO, CONFIRM = range(5)

CB_CANCEL = "addloc_cancel"
CB_SKIP_DESC = "addloc_skip_desc"
CB_SKIP_PHOTO = "addloc_skip_photo"
CB_CONFIRM = "addloc_confirm"


# ---------- UI helpers ----------
def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отменить", callback_data=CB_CANCEL)]])


def _description_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏭ Пропустить описание", callback_data=CB_SKIP_DESC)],
            [InlineKeyboardButton("❌ Отменить", callback_data=CB_CANCEL)],
        ]
    )


def _photo_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏭ Пропустить фото", callback_data=CB_SKIP_PHOTO)],
            [InlineKeyboardButton("❌ Отменить", callback_data=CB_CANCEL)],
        ]
    )


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Подтвердить", callback_data=CB_CONFIRM)],
            [InlineKeyboardButton("❌ Отменить", callback_data=CB_CANCEL)],
        ]
    )


def _clear_flow_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in (
        "loc_name",
        "loc_description",
        "latitude",
        "longitude",
        "photos",
        "add_location_message_id",
    ):
        context.user_data.pop(key, None)


async def _delete_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    try:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
        )
    except Exception:
        pass


async def _render_flow_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text_value: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    chat_id = update.effective_user.id
    message_id = context.user_data.get("add_location_message_id")

    if update.callback_query and not message_id:
        message_id = update.callback_query.message.message_id
        context.user_data["add_location_message_id"] = message_id

    if message_id:
        try:
            await context.bot.edit_message_text(
                text_value,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
            )
            return
        except BadRequest as exc:
            if "Message is not modified" in str(exc):
                return
            if "message to edit not found" not in str(exc).lower():
                raise

    source = update.callback_query.message if update.callback_query else update.message
    sent = await source.reply_text(text_value, reply_markup=reply_markup)
    context.user_data["add_location_message_id"] = sent.message_id


async def _show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    unread = bool(context.bot_data.get("mod_unread_tickets"))
    menu_id = context.user_data.get("main_menu_message_id")
    chat_id = update.effective_user.id
    if menu_id:
        try:
            await context.bot.edit_message_text(
                "Главное меню:",
                chat_id=chat_id,
                message_id=menu_id,
                reply_markup=get_main_menu(chat_id, unread_moderation=unread),
            )
            return
        except BadRequest:
            pass

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text="Главное меню:",
        reply_markup=get_main_menu(chat_id, unread_moderation=unread),
    )
    context.user_data["main_menu_message_id"] = sent.message_id


# ---------- handlers ----------
async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _clear_flow_data(context)
    if update.callback_query:
        await update.callback_query.answer()
    await _render_flow_message(update, context, "📍 Введи название локации:", _cancel_keyboard())
    return ASK_NAME


async def ask_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["loc_name"] = update.message.text.strip()
    await _delete_user_message(update, context)
    await _render_flow_message(update, context, "✏️ Напиши краткое описание:", _description_keyboard())
    return ASK_DESCRIPTION


async def ask_coords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["loc_description"] = update.message.text.strip()
    await _delete_user_message(update, context)
    await _render_flow_message(
        update,
        context,
        "📌 Отправь точку на карте (скрепка → Геопозиция → Выбрать место на карте).",
        _cancel_keyboard(),
    )
    return ASK_LOCATION


async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["loc_description"] = None
    await _render_flow_message(
        update,
        context,
        "📌 Отправь точку на карте (скрепка → Геопозиция → Выбрать место на карте).",
        _cancel_keyboard(),
    )
    return ASK_LOCATION


async def get_coords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.location:
        await _delete_user_message(update, context)
        await _render_flow_message(
            update,
            context,
            "⚠️ Нужна геопозиция. Выбери точку на карте и отправь её.",
            _cancel_keyboard(),
        )
        return ASK_LOCATION

    loc = update.message.location
    context.user_data["latitude"] = loc.latitude
    context.user_data["longitude"] = loc.longitude
    await _delete_user_message(update, context)
    await _render_flow_message(
        update,
        context,
        "📷 Отправь фото места (можно несколько) или пропусти шаг.",
        _photo_keyboard(),
    )
    return ASK_PHOTO


async def collect_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        context.user_data.setdefault("photos", []).append(file_id)
        await _delete_user_message(update, context)
        await _render_flow_message(
            update,
            context,
            f"📷 Фото добавлено: {len(context.user_data.get('photos', []))}. Можно отправить ещё или пропустить.",
            _photo_keyboard(),
        )
        return ASK_PHOTO

    await _delete_user_message(update, context)
    await _render_flow_message(update, context, "⚠️ Отправь фото или нажми «Пропустить фото».", _photo_keyboard())
    return ASK_PHOTO


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()

    d = context.user_data
    msg = (
        "🧾 Проверь данные:\n"
        f"🏷 Название: {d['loc_name']}\n"
        f"✏️ Описание: {d.get('loc_description') or '—'}\n"
        f"🌍 Координаты: {d['latitude']}, {d['longitude']}\n"
        f"📷 Фото: {len(d.get('photos', []))}\n\n"
        "Подтвердить отправку?"
    )
    await _render_flow_message(update, context, msg, _confirm_keyboard())
    return CONFIRM


async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await confirm(update, context)


async def save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()

    user = update.effective_user
    d = context.user_data
    achievements = AchievementsManager()

    with get_db_context() as db:
        get_or_create_user(db, user)
        loc = LocationService.create_location(
            db,
            user_id=user.id,
            name=d["loc_name"],
            latitude=d["latitude"],
            longitude=d["longitude"],
            description=d.get("loc_description"),
        )
        for i, file_id in enumerate(d.get("photos", [])):
            LocationService.add_photo(db, loc.id, file_id, order_index=i)
        achievements.apply_event(db, user.id, "location_submitted", 1)

    flow_message_id = context.user_data.get("add_location_message_id")
    if flow_message_id:
        try:
            await context.bot.delete_message(chat_id=user.id, message_id=flow_message_id)
        except Exception:
            pass

    _clear_flow_data(context)
    await _show_main_menu(update, context)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer("Добавление отменено")

    flow_message_id = context.user_data.get("add_location_message_id")
    if flow_message_id:
        try:
            await context.bot.delete_message(chat_id=update.effective_user.id, message_id=flow_message_id)
        except Exception:
            pass

    _clear_flow_data(context)
    await _show_main_menu(update, context)
    return ConversationHandler.END


add_location_handler = ConversationHandler(
    entry_points=[
        CommandHandler("add", start_add),
        MessageHandler(filters.Regex("^(➕ Добавить|add)$"), start_add),
        CallbackQueryHandler(start_add, pattern="^add_location$"),
    ],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_description)],
        ASK_DESCRIPTION: [
            CallbackQueryHandler(skip_description, pattern=f"^{CB_SKIP_DESC}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, ask_coords),
        ],
        ASK_LOCATION: [MessageHandler(filters.LOCATION, get_coords)],
        ASK_PHOTO: [
            CallbackQueryHandler(skip_photo, pattern=f"^{CB_SKIP_PHOTO}$"),
            MessageHandler(filters.PHOTO, collect_photo),
            MessageHandler(filters.TEXT & ~filters.COMMAND, collect_photo),
        ],
        CONFIRM: [CallbackQueryHandler(save, pattern=f"^{CB_CONFIRM}$")],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(cancel, pattern=f"^{CB_CANCEL}$"),
    ],
    allow_reentry=True,
)
