import json

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
from bot.models.tag import Tag
from bot.services.achievements_manager import AchievementsManager
from bot.services.location_service import LocationService
from bot.utils.section_banners import get_section_banner, send_section_banner
from bot.utils.users import get_or_create_user
from bot.utils.webapp import build_webapp_url

ASK_NAME, ASK_DESCRIPTION, ASK_LOCATION, ASK_TAG_CATEGORY, ASK_TAG_PICK, ASK_PHOTO, CONFIRM = range(7)

CB_CANCEL = "addloc_cancel"
CB_SKIP_DESC = "addloc_skip_desc"
CB_CONFIRM = "addloc_confirm"
CB_PHOTO_DONE = "addloc_photo_done"
CB_TAG_CAT = "addloc_tag_cat_"
CB_TAG_TOGGLE = "addloc_tag_toggle_"
CB_TAG_DONE = "addloc_tag_done"
CB_TAG_SKIP = "addloc_tag_skip"
CB_TAG_CLEAR = "addloc_tag_clear"
CB_TAG_BACK = "addloc_tag_back"

MAX_SELECTED_TAGS = 5
TAG_CATALOG = {
    "Еда": ["кафе", "ресторан", "бар", "фастфуд", "пекарня"],
    "Отдых": ["парк", "лес", "озеро", "река", "пляж", "смотровая площадка", "место для прогулки"],
    "Город": ["магазин", "рынок", "торговый центр", "спортзал", "коворкинг", "библиотека", "учебное место"],
    "Культура": ["историческое место", "памятник", "музей", "архитектура", "церковь", "заброшенное", "культурное место"],
    "Развлечения": ["кино", "клуб", "концертная площадка", "арт-пространство", "игровое место", "мероприятие", "ночное место"],
    "Атмосфера": ["тихое", "уютное", "популярное", "скрытое", "туристическое", "фотогеничное"],
    "Активности": ["прогулка", "пикник", "работа", "свидание", "спорт", "фотосъёмка", "отдых"],
    "Доступность": ["бесплатно", "платно", "круглосуточно", "семейное место", "подходит для детей", "можно с животными"],
}


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отменить", callback_data=CB_CANCEL)]])


def _description_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏭ Пропустить описание", callback_data=CB_SKIP_DESC)],
            [InlineKeyboardButton("❌ Отменить", callback_data=CB_CANCEL)],
        ]
    )


def _location_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗺️ Открыть карту", web_app={"url": build_webapp_url("/map?picker=1")})],
            [InlineKeyboardButton("❌ Отменить", callback_data=CB_CANCEL)],
        ]
    )


def _photo_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Подтвердить", callback_data=CB_PHOTO_DONE)],
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


def _get_selected_tag_ids(context: ContextTypes.DEFAULT_TYPE) -> set[int]:
    return set(context.user_data.get("selected_tag_ids", []))


def _set_selected_tag_ids(context: ContextTypes.DEFAULT_TYPE, tag_ids: set[int]) -> None:
    context.user_data["selected_tag_ids"] = list(tag_ids)


def _tag_categories_keyboard(selected_count: int) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(category, callback_data=f"{CB_TAG_CAT}{category}")] for category in TAG_CATALOG]
    rows.extend(
        [
            [InlineKeyboardButton(f"✅ Готово ({selected_count}/{MAX_SELECTED_TAGS})", callback_data=CB_TAG_DONE)],
            [InlineKeyboardButton("🧹 Очистить всё", callback_data=CB_TAG_CLEAR)],
            [InlineKeyboardButton("⏭ Пропустить", callback_data=CB_TAG_SKIP)],
            [InlineKeyboardButton("❌ Отменить", callback_data=CB_CANCEL)],
        ]
    )
    return InlineKeyboardMarkup(rows)


def _tag_pick_keyboard(category: str, tags: list[Tag], selected_ids: set[int]) -> InlineKeyboardMarkup:
    rows = []
    for tag in tags:
        selected_mark = "✅ " if tag.id in selected_ids else ""
        rows.append([InlineKeyboardButton(f"{selected_mark}{tag.name}", callback_data=f"{CB_TAG_TOGGLE}{tag.id}")])

    rows.extend(
        [
            [InlineKeyboardButton("◀️ Назад к категориям", callback_data=CB_TAG_BACK)],
            [InlineKeyboardButton("✅ Готово", callback_data=CB_TAG_DONE)],
            [InlineKeyboardButton("🧹 Очистить всё", callback_data=CB_TAG_CLEAR)],
            [InlineKeyboardButton("❌ Отменить", callback_data=CB_CANCEL)],
        ]
    )
    return InlineKeyboardMarkup(rows)


def _clear_flow_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in (
        "loc_name",
        "loc_description",
        "latitude",
        "longitude",
        "photos",
        "selected_tag_ids",
        "current_tag_category",
        "add_location_message_id",
    ):
        context.user_data.pop(key, None)


async def _delete_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
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
            await context.bot.edit_message_text(text_value, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
            return
        except BadRequest as exc:
            error_text = str(exc).lower()
            if "message is not modified" in error_text:
                return
            if "there is no text in the message to edit" in error_text:
                context.user_data.pop("add_location_message_id", None)
            elif "message to edit not found" not in error_text:
                raise

    source = update.callback_query.message if update.callback_query else update.message
    sent = await source.reply_text(text_value, reply_markup=reply_markup)
    context.user_data["add_location_message_id"] = sent.message_id


async def _show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    banner = get_section_banner("main_menu")
    caption = f"<b>{banner['title']}</b>\n\n{banner['description']}"
    await send_section_banner(
        update,
        context,
        "main_menu",
        caption,
        reply_markup=get_main_menu(update.effective_user.id),
        store_message_key="main_menu_message_id",
    )


async def _render_tag_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_ids = _get_selected_tag_ids(context)
    text = (
        "🏷️ Выбери категорию тегов\n"
        f"Выбрано: {len(selected_ids)}/{MAX_SELECTED_TAGS}.\n"
        "Можно выбирать теги из нескольких категорий."
    )
    await _render_flow_message(update, context, text, _tag_categories_keyboard(len(selected_ids)))
    return ASK_TAG_CATEGORY


async def _render_category_tags(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str) -> int:
    selected_ids = _get_selected_tag_ids(context)
    with get_db_context() as db:
        tags = db.query(Tag).filter(Tag.category == category).order_by(Tag.name.asc()).all()

    context.user_data["current_tag_category"] = category
    text = (
        f"📂 Категория: {category}\n"
        f"Выбрано всего: {len(selected_ids)}/{MAX_SELECTED_TAGS}\n"
        "Нажми на тег, чтобы выбрать/снять выбор."
    )
    await _render_flow_message(update, context, text, _tag_pick_keyboard(category, tags, selected_ids))
    return ASK_TAG_PICK


async def _proceed_to_photo_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _render_flow_message(
        update,
        context,
        "📷 Отправь хотя бы одно фото места. Можно отправить несколько.",
        _photo_keyboard(),
    )
    return ASK_PHOTO


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
        "📌 Выбери точку на карте и отправь геопозицию. Текущую геопозицию отправлять не нужно.",
        _location_keyboard(),
    )
    return ASK_LOCATION


async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["loc_description"] = None
    await _render_flow_message(
        update,
        context,
        "📌 Выбери точку на карте и отправь геопозицию. Текущую геопозицию отправлять не нужно.",
        _location_keyboard(),
    )
    return ASK_LOCATION


async def get_coords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    lat = None
    lng = None

    if message and message.location:
        lat = message.location.latitude
        lng = message.location.longitude
    elif message and message.web_app_data and message.web_app_data.data:
        try:
            payload = json.loads(message.web_app_data.data)
            if payload.get("type") == "add_location_point":
                lat = float(payload.get("latitude"))
                lng = float(payload.get("longitude"))
        except (TypeError, ValueError, json.JSONDecodeError):
            lat = None
            lng = None

    if lat is None or lng is None:
        await _delete_user_message(update, context)
        await _render_flow_message(
            update,
            context,
            "⚠️ Нужна геопозиция. Открой карту, поставь метку и нажми «Подтвердить точку».",
            _location_keyboard(),
        )
        return ASK_LOCATION

    context.user_data["latitude"] = lat
    context.user_data["longitude"] = lng
    await _delete_user_message(update, context)

    with get_db_context() as db:
        LocationService.ensure_tags(db, TAG_CATALOG)

    return await _render_tag_categories(update, context)


async def open_tag_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.replace(CB_TAG_CAT, "", 1)
    if category not in TAG_CATALOG:
        await query.answer("Категория не найдена", show_alert=True)
        return ASK_TAG_CATEGORY
    return await _render_category_tags(update, context, category)


async def toggle_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tag_id = int(query.data.replace(CB_TAG_TOGGLE, "", 1))
    selected = _get_selected_tag_ids(context)

    if tag_id in selected:
        selected.remove(tag_id)
    else:
        if len(selected) >= MAX_SELECTED_TAGS:
            await query.answer(f"Можно выбрать не более {MAX_SELECTED_TAGS} тегов", show_alert=True)
            return ASK_TAG_PICK
        selected.add(tag_id)

    _set_selected_tag_ids(context, selected)
    category = context.user_data.get("current_tag_category")
    if not category:
        return await _render_tag_categories(update, context)
    return await _render_category_tags(update, context, category)


async def tags_back_to_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await _render_tag_categories(update, context)


async def tags_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await _proceed_to_photo_step(update, context)


async def tags_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["selected_tag_ids"] = []
    return await _proceed_to_photo_step(update, context)


async def tags_clear_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Выбор тегов очищен")
    context.user_data["selected_tag_ids"] = []
    category = context.user_data.get("current_tag_category")
    if category and update.callback_query.message and "Категория:" in update.callback_query.message.text:
        return await _render_category_tags(update, context, category)
    return await _render_tag_categories(update, context)


async def collect_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        context.user_data.setdefault("photos", []).append(file_id)
        await _delete_user_message(update, context)
        photos_count = len(context.user_data.get('photos', []))
        await _render_flow_message(
            update,
            context,
            f"📷 Фото добавлено: {photos_count}. "
            f"Отправь ещё фото или нажми «Подтвердить», когда закончишь.",
            _photo_keyboard(),
        )
        return ASK_PHOTO

    await _delete_user_message(update, context)
    await _render_flow_message(update, context, "⚠️ Отправь фото места, пропустить этот шаг нельзя.", _photo_keyboard())
    return ASK_PHOTO


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()

    d = context.user_data
    selected_ids = _get_selected_tag_ids(context)
    tag_line = "—"
    if selected_ids:
        with get_db_context() as db:
            tags = db.query(Tag).filter(Tag.id.in_(selected_ids)).order_by(Tag.category.asc(), Tag.name.asc()).all()
            tag_line = ", ".join(f"{t.name} ({t.category})" for t in tags) if tags else "—"

    msg = (
        "🧾 Проверь данные:\n"
        f"🏷 Название: {d['loc_name']}\n"
        f"✏️ Описание: {d.get('loc_description') or '—'}\n"
        f"🌍 Координаты: {d['latitude']}, {d['longitude']}\n"
        f"🏷️ Теги: {tag_line}\n"
        f"📷 Фото: {len(d.get('photos', []))}\n\n"
        "Подтвердить отправку?"
    )
    await _render_flow_message(update, context, msg, _confirm_keyboard())
    return CONFIRM


async def save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()

    user = update.effective_user
    d = context.user_data
    selected_ids = list(_get_selected_tag_ids(context))
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
        if selected_ids:
            LocationService.add_tags_by_ids(db, loc.id, selected_ids)
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
        ASK_LOCATION: [
            MessageHandler(filters.LOCATION, get_coords),
            MessageHandler(filters.StatusUpdate.WEB_APP_DATA, get_coords),
        ],
        ASK_TAG_CATEGORY: [
            CallbackQueryHandler(open_tag_category, pattern=f"^{CB_TAG_CAT}"),
            CallbackQueryHandler(tags_done, pattern=f"^{CB_TAG_DONE}$"),
            CallbackQueryHandler(tags_skip, pattern=f"^{CB_TAG_SKIP}$"),
            CallbackQueryHandler(tags_clear_all, pattern=f"^{CB_TAG_CLEAR}$"),
        ],
        ASK_TAG_PICK: [
            CallbackQueryHandler(toggle_tag, pattern=f"^{CB_TAG_TOGGLE}"),
            CallbackQueryHandler(tags_back_to_categories, pattern=f"^{CB_TAG_BACK}$"),
            CallbackQueryHandler(tags_done, pattern=f"^{CB_TAG_DONE}$"),
            CallbackQueryHandler(tags_clear_all, pattern=f"^{CB_TAG_CLEAR}$"),
        ],
        ASK_PHOTO: [
            CallbackQueryHandler(confirm, pattern=f"^{CB_PHOTO_DONE}$"),
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
