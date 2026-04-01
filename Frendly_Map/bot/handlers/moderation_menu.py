import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, Update, WebAppInfo
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
from bot.models.user import User
from bot.services.gp_service import GPService
from bot.utils.common import is_admin
from bot.utils.section_banners import get_section_banner, send_section_banner
from bot.utils.webapp import build_webapp_url

POINTS_ACTION, POINTS_TYPE, POINTS_SELECT_USER, POINTS_AMOUNT, POINTS_CUSTOM = range(5)
logger = logging.getLogger(__name__)

def _ensure_admin(update: Update) -> bool:
    return is_admin(update.effective_user.id)


def _moderation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📍 Модерация локаций", callback_data="mod_locations")],
        [InlineKeyboardButton("⚖️ Баллы и ранги", callback_data="mod_points")],
        [InlineKeyboardButton("🗑 Удаление локаций", callback_data="mod_delete_location")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])


async def _safe_edit_menu_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    text_value: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    try:
        await context.bot.edit_message_text(
            text_value,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )
        return True
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            return False
        raise


async def _render_points_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db_context() as db:
        users = db.query(User).order_by(User.id.desc()).limit(20).all()

    if not users:
        await _show_moderation_menu(update, context)
        return

    keyboard = []
    for user in users:
        label = f"@{user.username}" if user.username else "Без ника"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"points_user_{user.id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="mod_points")])
    menu_message_id = context.user_data.get("moderation_menu_message_id")
    header = "Выберите пользователя:"
    flash = context.user_data.pop("points_flash", None)
    if flash:
        header = f"{flash}\n\nВыберите пользователя:"

    if menu_message_id:
        await context.bot.edit_message_text(
            header,
            chat_id=update.effective_user.id,
            message_id=menu_message_id,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        sent = await update.message.reply_text(
            header,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data["moderation_menu_message_id"] = sent.message_id


async def _show_moderation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_message_id = context.user_data.get("moderation_menu_message_id")
    text_value = "⚙️ Панель модерации:"
    if menu_message_id:
        await context.bot.edit_message_text(
            text_value,
            chat_id=update.effective_user.id,
            message_id=menu_message_id,
            reply_markup=_moderation_keyboard()
        )
    else:
        sent = await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=text_value,
            reply_markup=_moderation_keyboard()
        )
        context.user_data["moderation_menu_message_id"] = sent.message_id


async def moderation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _ensure_admin(update):
        chat = update.callback_query.message if update.callback_query else update.message
        if update.callback_query:
            await update.callback_query.answer()
        await chat.reply_text("⛔ Только для модераторов.")
        return

    banner = get_section_banner("moderation")
    banner_caption = f"<b>{banner['title']}</b>\n{banner['description']}"
    await send_section_banner(
        update,
        context,
        "moderation",
        banner_caption,
        delete_origin=True,
    )

    context.user_data.pop("moderation_menu_message_id", None)
    await _show_moderation_menu(update, context)


async def moderation_locations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _ensure_admin(update):
        await query.edit_message_text("⛔ Только для модераторов.")
        return

    with get_db_context() as db:
        locations = db.query(Location).filter(Location.status == "pending").order_by(Location.created_at.asc()).limit(20).all()

    if not locations:
        await query.edit_message_text(
            "📍 Модерация локаций\n\nСейчас нет локаций на модерацию.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="moderation")]]),
        )
        return

    keyboard = [
        [InlineKeyboardButton(f"{loc.name} (#{loc.id})", callback_data=f"loc_detail_{loc.id}")]
        for loc in locations
    ]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="moderation")])
    await query.edit_message_text(
        "📍 Модерация локаций\nВыберите локацию:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def points_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _ensure_admin(update):
        await query.message.reply_text("⛔ Только для модераторов.")
        return ConversationHandler.END

    context.user_data.pop("points_data", None)
    context.user_data["moderation_menu_message_id"] = query.message.message_id
    await query.edit_message_text(
        "Что сделать?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ Начислить", callback_data="points_add"),
                InlineKeyboardButton("➖ Списать", callback_data="points_sub"),
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data="moderation")],
        ])
    )
    return POINTS_ACTION


async def points_choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = "add" if query.data == "points_add" else "sub"
    context.user_data["points_data"] = {"action": action}
    await query.edit_message_text(
        "Что изменить?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⭐ Баллы", callback_data="points_type_regular"),
                InlineKeyboardButton("🎯 Ранговые очки", callback_data="points_type_rank"),
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data="mod_points")],
        ])
    )
    return POINTS_TYPE


async def points_select_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[-1])
    context.user_data.setdefault("points_data", {})["user_id"] = user_id
    action_label = "Начислить" if context.user_data.get("points_data", {}).get("action") == "add" else "Списать"
    type_label = "баллы" if context.user_data.get("points_data", {}).get("type") == "regular" else "ранговые очки"
    await query.edit_message_text(
        f"{action_label} {type_label}. Выберите количество:",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("1", callback_data="points_amount_1"),
                InlineKeyboardButton("5", callback_data="points_amount_5"),
                InlineKeyboardButton("10", callback_data="points_amount_10"),
            ],
            [
                InlineKeyboardButton("20", callback_data="points_amount_20"),
                InlineKeyboardButton("Другое", callback_data="points_amount_custom"),
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data="points_type_back")],
        ])
    )
    return POINTS_AMOUNT


async def points_choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    points_type = "regular" if query.data == "points_type_regular" else "rank"
    context.user_data.setdefault("points_data", {})["type"] = points_type
    await _render_points_users(update, context)
    return POINTS_SELECT_USER


def _apply_points_change(db, data: dict, amount: int):
    delta = amount if data.get("action") == "add" else -amount
    user = db.query(User).filter(User.id == data["user_id"]).first()
    if not user:
        return None, None

    if data.get("type") == "rank":
        rank_data = GPService.add_gp(db, user.id, delta)
        if rank_data is None:
            return None, None
        new_value = rank_data["total_gp"]
        label = "ранговых"
    else:
        user.points = max(user.points + delta, 0)
        new_value = user.points
        label = "обычных"
        db.commit()
    return new_value, label


async def points_apply(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int | None = None):
    data = context.user_data.get("points_data", {})
    if "user_id" not in data:
        return ConversationHandler.END

    if amount is None:
        try:
            amount = int(update.message.text.strip())
        except ValueError:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
            except Exception:
                pass
            menu_message_id = context.user_data.get("moderation_menu_message_id")
            if menu_message_id:
                await _safe_edit_menu_message(context, update.effective_user.id, menu_message_id, "Введите целое число:")
            return POINTS_CUSTOM

    with get_db_context() as db:
        new_value, label = _apply_points_change(db, data, amount)

    if new_value is None:
        return ConversationHandler.END

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass
    context.user_data["points_flash"] = f"✅ Новый баланс {label} баллов: {new_value}"
    context.user_data.pop("points_data", None)
    await _render_points_users(update, context)
    return POINTS_SELECT_USER


async def points_amount_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split("_")[-1]
    if choice == "custom":
        await query.edit_message_text("Введите число:")
        return POINTS_CUSTOM
    amount = int(choice)
    data = context.user_data.get("points_data", {})
    with get_db_context() as db:
        new_value, label = _apply_points_change(db, data, amount)

    if new_value is None:
        return ConversationHandler.END

    context.user_data["points_flash"] = f"✅ Новый баланс {label} баллов: {new_value}"
    context.user_data.pop("points_data", None)
    await _render_points_users(update, context)
    return POINTS_SELECT_USER


async def points_type_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("points_data", None)
    await points_start(update, context)
    return POINTS_ACTION


async def delete_location_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _ensure_admin(update):
        await query.message.reply_text("⛔ Только для модераторов.")
        return

    delete_url = build_webapp_url("/map?mod_delete=1&moderation=1")
    logger.info(
        "Delete mode opened",
        extra={"moderator_id": update.effective_user.id, "delete_url": delete_url},
    )
    await query.edit_message_text(
        "🗑 Удаление локаций через карту.\n\nОткрой карту, выбери локацию и подтверди удаление.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗺 Удалить через карту", web_app=WebAppInfo(url=delete_url))],
            [InlineKeyboardButton("◀️ Назад", callback_data="moderation")],
        ]),
    )


async def delete_locations_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("delete_locations_active"):
        return
    context.user_data.pop("delete_locations_active", None)
    await update.message.reply_text("\u2060", reply_markup=ReplyKeyboardRemove())
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass
    await _show_moderation_menu(update, context)


moderation_menu_handler = CommandHandler("moderation", moderation_menu)
moderation_menu_callback = CallbackQueryHandler(moderation_menu, pattern="^moderation$")
moderation_locations_handler = CallbackQueryHandler(moderation_locations, pattern="^mod_locations$")

points_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(points_start, pattern="^mod_points$")],
    states={
        POINTS_ACTION: [CallbackQueryHandler(points_choose_action, pattern="^points_(add|sub)$")],
        POINTS_TYPE: [
            CallbackQueryHandler(points_choose_type, pattern="^points_type_(regular|rank)$"),
            CallbackQueryHandler(points_type_back, pattern="^points_type_back$"),
        ],
        POINTS_SELECT_USER: [CallbackQueryHandler(points_select_user, pattern="^points_user_\\d+$")],
        POINTS_AMOUNT: [CallbackQueryHandler(points_amount_choice, pattern="^points_amount_")],
        POINTS_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, points_apply)],
    },
    fallbacks=[CommandHandler("cancel", moderation_menu)],
    allow_reentry=True,
)

delete_location_handler = CallbackQueryHandler(delete_location_start, pattern="^mod_delete_location$")

moderation_delete_back_handler = MessageHandler(filters.Regex("^◀️ Назад$"), delete_locations_back)
