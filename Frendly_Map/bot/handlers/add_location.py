import asyncio
import json
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext._utils.types import CCT
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
from bot.models.webapp_pick import WebAppPick
from bot.services.achievements_manager import AchievementsManager
from bot.services.location_service import LocationService
from bot.utils.section_banners import get_section_banner, send_section_banner
from bot.utils.users import get_or_create_user
from bot.utils.webapp import build_webapp_url

ASK_NAME, ASK_DESCRIPTION, ASK_LOCATION, ASK_PHOTO, CONFIRM = range(5)

CB_CANCEL = "addloc_cancel"
CB_SKIP_DESC = "addloc_skip_desc"
CB_CONFIRM = "addloc_confirm"
CB_PHOTO_DONE = "addloc_photo_done"
WEBAPP_FLOW_ADD_LOCATION = "add_location"
GEO_JOB_PREFIX = "addloc_geo_poll_"
GEO_TASK_PREFIX = "addloc_geo_task_"
CANCEL_TEXT = "❌ Отменить"
logger = logging.getLogger(__name__)

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


def _geo_job_name(user_id: int) -> str:
    return f"{GEO_JOB_PREFIX}{user_id}"


def _geo_task_name(user_id: int) -> str:
    return f"{GEO_TASK_PREFIX}{user_id}"


def _conversation_key(chat_id: int, user_id: int) -> tuple[int, int]:
    return chat_id, user_id


async def _schedule_geo_pick_poll(context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int) -> None:
    if context.job_queue is not None:
        job_name = _geo_job_name(user_id)
        for job in context.job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()

        logger.info("Started geo-pick job polling", extra={"user_id": user_id, "chat_id": chat_id})
        context.job_queue.run_repeating(
            _poll_geo_pick_job,
            interval=1.0,
            first=1.0,
            name=job_name,
            data={"user_id": user_id, "chat_id": chat_id},
        )
        return

    task_name = _geo_task_name(user_id)
    task = context.application.bot_data.get(task_name)
    if task and not task.done():
        task.cancel()
        logger.info("Stopped geo-pick async polling task", extra={"user_id": user_id})

    logger.info("Started geo-pick async polling task", extra={"user_id": user_id, "chat_id": chat_id})
    context.application.bot_data[task_name] = context.application.create_task(
        _poll_geo_pick_task(context.application, user_id, chat_id)
    )


def _stop_geo_pick_poll(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    if context.job_queue is not None:
        for job in context.job_queue.get_jobs_by_name(_geo_job_name(user_id)):
            job.schedule_removal()

    task_name = _geo_task_name(user_id)
    task = context.application.bot_data.pop(task_name, None)
    if task and not task.done():
        task.cancel()
        logger.info("Stopped geo-pick async polling task", extra={"user_id": user_id})


def _clear_pending_geo_pick(user_id: int, chat_id: int) -> None:
    with get_db_context() as db:
        db.query(WebAppPick).filter(
            WebAppPick.user_id == user_id,
            WebAppPick.chat_id == chat_id,
            WebAppPick.flow == WEBAPP_FLOW_ADD_LOCATION,
            WebAppPick.processed.is_(False),
        ).delete()
        db.commit()


class _SyntheticMessage:
    def __init__(self, bot, chat_id: int):
        self._bot = bot
        self.chat_id = chat_id

    async def reply_text(self, text: str, reply_markup=None):
        return await self._bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)


class _SyntheticUpdate:
    def __init__(self, bot, user_id: int, chat_id: int):
        self.callback_query = None
        self.message = _SyntheticMessage(bot, chat_id)
        self.effective_chat = type("Chat", (), {"id": chat_id})()
        self.effective_user = type("User", (), {"id": user_id})()


async def _poll_geo_pick_job(context: CCT):
    user_id = context.job.data["user_id"]
    chat_id = context.job.data["chat_id"]
    await _advance_from_pending_pick(context.application, context.bot, user_id, chat_id)


async def _poll_geo_pick_task(application, user_id: int, chat_id: int):
    try:
        while True:
            advanced = await _advance_from_pending_pick(application, application.bot, user_id, chat_id)
            if advanced:
                return
            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        return


async def _advance_from_pending_pick(application, bot, user_id: int, chat_id: int) -> bool:
    with get_db_context() as db:
        pick = (
            db.query(WebAppPick)
            .filter(
                WebAppPick.user_id == user_id,
                WebAppPick.chat_id == chat_id,
                WebAppPick.flow == WEBAPP_FLOW_ADD_LOCATION,
                WebAppPick.processed.is_(False),
            )
            .order_by(WebAppPick.id.desc())
            .first()
        )
        if not pick:
            logger.debug("No pending geo-pick record", extra={"user_id": user_id, "chat_id": chat_id, "flow": WEBAPP_FLOW_ADD_LOCATION})
            return False

        logger.info("Geo-pick record found", extra={"user_id": user_id, "chat_id": chat_id, "pick_id": pick.id, "flow": WEBAPP_FLOW_ADD_LOCATION})
        pick.processed = True
        lat = pick.latitude
        lng = pick.longitude
        db.commit()

    try:
        user_data = application.user_data[user_id]
    except KeyError:
        user_data = application._user_data.setdefault(user_id, {})

    user_data["latitude"] = lat
    user_data["longitude"] = lng
    logger.debug(
        "Stored geo coordinates in user_data",
        extra={"user_id": user_id, "chat_id": chat_id, "latitude": lat, "longitude": lng},
    )

    with get_db_context() as db:
        LocationService.ensure_tags(db, TAG_CATALOG)

    tag_ids: list[int] = []
    raw_tag_ids = getattr(pick, "tag_ids_json", None)
    if raw_tag_ids:
        try:
            parsed = json.loads(raw_tag_ids)
            if isinstance(parsed, list):
                tag_ids = [int(x) for x in parsed if isinstance(x, int) or (isinstance(x, str) and x.isdigit())]
        except json.JSONDecodeError:
            logger.warning("Invalid picker tag_ids_json payload", extra={"user_id": user_id, "chat_id": chat_id})
    user_data["selected_tag_ids"] = sorted(set(tag_ids))[:5]

    add_location_handler._conversations[_conversation_key(chat_id, user_id)] = ASK_PHOTO
    logger.debug("Set conversation state to ASK_PHOTO", extra={"user_id": user_id, "chat_id": chat_id})
    synthetic_update = _SyntheticUpdate(bot, user_id, chat_id)

    fake_context = type("Ctx", (), {"bot": bot, "user_data": user_data})()
    await _proceed_to_photo_step(synthetic_update, fake_context)
    logger.info("Advanced add-location conversation after geo-pick", extra={"user_id": user_id, "chat_id": chat_id, "next_state": ASK_PHOTO, "tag_ids_count": len(user_data['selected_tag_ids'])})

    task_name = _geo_task_name(user_id)
    task = application.bot_data.pop(task_name, None)
    if task and not task.done() and asyncio.current_task() is not task:
        task.cancel()
    return True


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(CANCEL_TEXT, callback_data=CB_CANCEL)]])


def _description_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏭ Пропустить описание", callback_data=CB_SKIP_DESC)],
            [InlineKeyboardButton(CANCEL_TEXT, callback_data=CB_CANCEL)],
        ]
    )


def _location_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗺️ Открыть карту", web_app={"url": build_webapp_url(f"/map?picker=1&chat_id={chat_id}")})],
            [InlineKeyboardButton(CANCEL_TEXT, callback_data=CB_CANCEL)],
        ]
    )


def _photo_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Подтвердить", callback_data=CB_PHOTO_DONE)],
            [InlineKeyboardButton(CANCEL_TEXT, callback_data=CB_CANCEL)],
        ]
    )


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Подтвердить", callback_data=CB_CONFIRM)],
            [InlineKeyboardButton(CANCEL_TEXT, callback_data=CB_CANCEL)],
        ]
    )


def _get_selected_tag_ids(context: ContextTypes.DEFAULT_TYPE) -> set[int]:
    return set(context.user_data.get("selected_tag_ids", []))


def _set_selected_tag_ids(context: ContextTypes.DEFAULT_TYPE, tag_ids: set[int]) -> None:
    context.user_data["selected_tag_ids"] = list(tag_ids)


def _clear_flow_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in (
        "loc_name",
        "loc_description",
        "latitude",
        "longitude",
        "photos",
        "selected_tag_ids",
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


async def _render_location_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, text_value: str) -> None:
    await _render_flow_message(update, context, text_value, _location_keyboard(update.effective_chat.id))


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
    await _render_location_prompt(
        update,
        context,
        "📌 Выбери точку на карте и подтверди её в Mini App. Затем выбери теги и подтверди.",
    )
    with get_db_context() as db:
        LocationService.ensure_tags(db, TAG_CATALOG)
    _clear_pending_geo_pick(update.effective_user.id, update.effective_chat.id)
    await _schedule_geo_pick_poll(context, update.effective_user.id, update.effective_chat.id)
    return ASK_LOCATION


async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["loc_description"] = None
    await _render_location_prompt(
        update,
        context,
        "📌 Выбери точку на карте и подтверди её в Mini App. Затем выбери теги и подтверди.",
    )
    with get_db_context() as db:
        LocationService.ensure_tags(db, TAG_CATALOG)
    _clear_pending_geo_pick(update.effective_user.id, update.effective_chat.id)
    await _schedule_geo_pick_poll(context, update.effective_user.id, update.effective_chat.id)
    return ASK_LOCATION


def _parse_webapp_coords(raw_payload: str) -> tuple[float | None, float | None]:
    raw = (raw_payload or "").strip()
    if not raw:
        return None, None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        source = payload
        if isinstance(payload.get("point"), dict):
            source = payload["point"]
        elif isinstance(payload.get("coords"), dict):
            source = payload["coords"]

        lat_raw = source.get("latitude", source.get("lat"))
        lng_raw = source.get("longitude", source.get("lng"))

        try:
            if lat_raw is not None and lng_raw is not None:
                return float(lat_raw), float(lng_raw)
        except (TypeError, ValueError):
            pass

    if "," in raw:
        try:
            raw_lat, raw_lng = raw.split(",", 1)
            return float(raw_lat.strip()), float(raw_lng.strip())
        except (TypeError, ValueError):
            return None, None

    return None, None


async def get_coords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    lat = None
    lng = None

    if message and message.location:
        lat = message.location.latitude
        lng = message.location.longitude
    elif message and message.text:
        lat, lng = _parse_webapp_coords(message.text)

    if lat is None or lng is None:
        await _delete_user_message(update, context)
        await _render_location_prompt(
            update,
            context,
            "⚠️ Нужна геопозиция. Открой карту, поставь метку и нажми «Подтвердить точку».",
        )
        return ASK_LOCATION

    context.user_data["latitude"] = lat
    context.user_data["longitude"] = lng
    await _delete_user_message(update, context)

    context.user_data["selected_tag_ids"] = []
    return await _proceed_to_photo_step(update, context)


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
    _stop_geo_pick_poll(context, user.id)
    _clear_pending_geo_pick(user.id, update.effective_chat.id)
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

    _stop_geo_pick_poll(context, update.effective_user.id)
    _clear_pending_geo_pick(update.effective_user.id, update.effective_chat.id)
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
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_coords),
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
