import logging
from html import escape
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, ConversationHandler, filters

from datetime import datetime
from bot.database import get_db_context
from bot.models.location import Location
from shared.models.moderation_followup import ModerationFollowup
from bot.models.user import User
from bot.utils.common import is_admin
from bot.utils.webapp import build_webapp_url
from bot.services.achievements_manager import AchievementsManager
from bot.services.gp_service import GPService
from bot.handlers.moderation_menu import moderation_menu
from bot.services.moderation_service import send_pending_locations

APPROVE_BASE_POINTS = 15
APPROVE_BASE_GP = 10
EXTRA_GP_LIMIT = 60
logger = logging.getLogger(__name__)
EXTRA_REWARD_AMOUNT = 0


async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_pending_locations(update.message, update.effective_user.id)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = update.effective_user.id
    if not is_admin(uid):
        await query.edit_message_text("⛔ Доступ запрещен.")
        return

    action, loc_id = query.data.split("_")
    loc_id = int(loc_id)
    context.user_data["moderation_menu_message_id"] = query.message.message_id

    achievements = AchievementsManager()
    completed = []

    with get_db_context() as db:
        loc = db.query(Location).filter(Location.id == loc_id).first()

        if not loc:
            await query.edit_message_text("⚠️ Локация не найдена")
            return

        owner = db.query(User).filter(User.id == loc.user_id).first()
        # изменение статуса
        if action == "approve":
            loc.status = "approved"
            loc.approved_by = uid
            loc.moderated_at = datetime.utcnow()
            if owner:
                owner.points += APPROVE_BASE_POINTS
                owner.approved_locations += 1
                owner.moderation_locations = max(owner.moderation_locations - 1, 0)
                GPService.add_gp(db, owner.id, APPROVE_BASE_GP)
                achievements.apply_event(
                    db,
                    owner.id,
                    "coins_earned",
                    APPROVE_BASE_POINTS,
                    event_key=f"approval_coins:{loc.id}",
                )
                completed = achievements.apply_event(
                    db,
                    owner.id,
                    "location_approved",
                    1,
                    event_key=f"approval:{loc.id}",
                )
                logger.info(
                    "Location approved",
                    extra={"location_id": loc.id, "moderator_id": uid, "owner_id": owner.id, "base_points": APPROVE_BASE_POINTS, "base_gp": APPROVE_BASE_GP},
                )
        elif action == "reject":
            loc.status = "rejected"
            loc.approved_by = uid
            loc.moderated_at = datetime.utcnow()
            if owner:
                owner.points = max(owner.points - 5, 0)
                owner.rejected_locations += 1
                owner.moderation_locations = max(owner.moderation_locations - 1, 0)
                achievements.apply_event(db, owner.id, "location_rejected", 1, event_key=f"reject:{loc.id}")
                logger.info("Location rejected", extra={"location_id": loc.id, "moderator_id": uid, "owner_id": owner.id})

        db.commit()

        # уведомление пользователя при approve/reject
        if owner:
            if action == "approve":
                await context.bot.send_message(
                    chat_id=owner.id,
                    text=f"🎉 Твоя локация <b>{loc.name}</b> была <b>одобрена</b>!",
                    parse_mode="HTML"
                )
                if completed:
                    await context.bot.send_message(
                        chat_id=owner.id,
                        text=achievements.format_completion_message(completed)
                    )
            else:
                await context.bot.send_message(
                    chat_id=owner.id,
                    text=f"😕 Локация <b>{loc.name}</b> была <b>отклонена</b>.",
                    parse_mode="HTML"
                )

    if action == "approve" and owner:
        context.user_data["extra_reward_location_id"] = loc_id
        context.user_data["extra_reward_user_id"] = owner.id
        await query.edit_message_text(
            "Локация одобрена ✅\n\nВыдать дополнительную награду?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Доп монеты", callback_data="extra_reward_coins")],
                [InlineKeyboardButton("🎯 Доп GP (до 60)", callback_data="extra_reward_gp")],
                [InlineKeyboardButton("⏭ Пропустить", callback_data="extra_reward_skip")],
            ]),
        )
        return

    await moderation_menu(update, context)


async def show_location_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = update.effective_user.id
    if not is_admin(uid):
        await query.edit_message_text("⛔ Доступ запрещен.")
        return

    loc_id = int(query.data.split("_")[-1])
    with get_db_context() as db:
        loc = db.query(Location).filter(Location.id == loc_id).first()
        owner = db.query(User).filter(User.id == loc.user_id).first() if loc else None

    if not loc:
        await query.edit_message_text("⚠️ Локация не найдена")
        return

    owner_name = f"@{owner.username}" if owner and owner.username else "Без ника"
    safe_name = escape(loc.name or "", quote=False)
    safe_desc = escape(loc.description or "Без описания", quote=False)
    safe_owner = escape(owner_name, quote=False)
    review_url = build_webapp_url(f"/map?moderation=1&focus_location_id={loc.id}")
    logger.info(
        "Moderation review URL built",
        extra={"moderator_id": uid, "location_id": loc.id, "review_url": review_url},
    )
    text = (
        f"📍 <b>{safe_name}</b>\n"
        f"📝 {safe_desc}\n"
        f"👤 Автор: {safe_owner}\n"
        f"🌍 {loc.latitude}, {loc.longitude}\n"
        f"🗺️ Статус: {escape(loc.status or '', quote=False)}"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✔️ Одобрить", callback_data=f"approve_{loc.id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{loc.id}"),
        ],
        [
            InlineKeyboardButton(
                "🗺️ Карта",
                web_app=WebAppInfo(url=review_url),
            )
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="mod_locations")],
    ])
    logger.info("Moderation review button clicked", extra={"moderator_id": uid, "location_id": loc.id})

    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


async def extra_reward_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("web_bonus_"):
        _, _, reward_type, followup_id_raw = query.data.split("_", 3)
        try:
            followup_id = int(followup_id_raw)
        except ValueError:
            await moderation_menu(update, context)
            return ConversationHandler.END
        with get_db_context() as db:
            followup = db.get(ModerationFollowup, followup_id)
            if not followup or followup.status != "pending" or followup.moderator_id != update.effective_user.id:
                await moderation_menu(update, context)
                return ConversationHandler.END
            if reward_type == "skip":
                followup.status = "handled"
                followup.handled_at = datetime.utcnow()
                db.commit()
                logger.info("Bonus step skipped", extra={"followup_id": followup_id, "moderator_id": update.effective_user.id})
                await moderation_menu(update, context)
                return ConversationHandler.END
            context.user_data["extra_reward_location_id"] = followup.location_id
            context.user_data["extra_reward_user_id"] = followup.owner_id
            context.user_data["extra_reward_followup_id"] = followup.id
            context.user_data["extra_reward_type"] = "coins" if reward_type == "coins" else "gp"
            prompt = "Введите количество доп монет:" if reward_type == "coins" else "Введите количество доп GP (1..60):"
            await query.edit_message_text(prompt)
            return EXTRA_REWARD_AMOUNT

    if not _can_apply_extra_reward(context):
        await moderation_menu(update, context)
        return

    if query.data == "extra_reward_skip":
        _clear_extra_reward_state(context)
        await moderation_menu(update, context)
        return ConversationHandler.END

    reward_type = "coins" if query.data == "extra_reward_coins" else "gp"
    context.user_data["extra_reward_type"] = reward_type
    prompt = "Введите количество доп монет:" if reward_type == "coins" else "Введите количество доп GP (1..60):"
    await query.edit_message_text(prompt)
    return EXTRA_REWARD_AMOUNT


async def extra_reward_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _can_apply_extra_reward(context):
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    try:
        amount = int(text)
    except ValueError:
        await update.message.reply_text("Введите целое число.")
        return EXTRA_REWARD_AMOUNT
    if amount <= 0:
        await update.message.reply_text("Число должно быть больше нуля.")
        return EXTRA_REWARD_AMOUNT

    reward_type = context.user_data.get("extra_reward_type")
    user_id = context.user_data.get("extra_reward_user_id")
    location_id = context.user_data.get("extra_reward_location_id")
    if reward_type == "gp" and amount > EXTRA_GP_LIMIT:
        await update.message.reply_text("Доп GP не может быть больше 60.")
        return EXTRA_REWARD_AMOUNT

    with get_db_context() as db:
        user = db.get(User, user_id)
        if not user:
            _clear_extra_reward_state(context)
            await update.message.reply_text("Пользователь не найден.")
            return ConversationHandler.END
        if reward_type == "gp":
            GPService.add_gp(db, user.id, amount)
            logger.info("Extra GP granted", extra={"location_id": location_id, "moderator_id": update.effective_user.id, "owner_id": user.id, "amount": amount})
        else:
            user.points += amount
            AchievementsManager().apply_event(
                db,
                user.id,
                "coins_earned",
                amount,
                event_key=f"extra_reward_coins:{location_id}:{user.id}:{amount}",
            )
            db.commit()
            logger.info("Extra coins granted", extra={"location_id": location_id, "moderator_id": update.effective_user.id, "owner_id": user.id, "amount": amount})
        followup_id = context.user_data.get("extra_reward_followup_id")
        if followup_id:
            followup = db.get(ModerationFollowup, int(followup_id))
            if followup and followup.status == "pending":
                followup.status = "handled"
                followup.handled_at = datetime.utcnow()
                db.commit()

    await update.message.reply_text("✅ Доп награда начислена.")
    _clear_extra_reward_state(context)
    await moderation_menu(update, context)
    return ConversationHandler.END


def _can_apply_extra_reward(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return bool(context.user_data.get("extra_reward_location_id") and context.user_data.get("extra_reward_user_id"))


def _clear_extra_reward_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in ("extra_reward_location_id", "extra_reward_user_id", "extra_reward_type", "extra_reward_followup_id"):
        context.user_data.pop(key, None)

pending_handler = CommandHandler("pending", pending)
moderation_callback_handler = CallbackQueryHandler(handle_callback, pattern="^(approve|reject)_[0-9]+$")
moderation_detail_handler = CallbackQueryHandler(show_location_detail, pattern="^loc_detail_\\d+$")
moderation_extra_reward_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(extra_reward_choice, pattern="^(extra_reward_(coins|gp|skip)|web_bonus_(coins|gp|skip)_\\d+)$")],
    states={EXTRA_REWARD_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, extra_reward_amount)]},
    fallbacks=[CommandHandler("cancel", moderation_menu)],
    allow_reentry=True,
)
