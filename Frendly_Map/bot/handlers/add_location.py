from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    MessageHandler, CommandHandler, ConversationHandler,
    ContextTypes, filters
)
from bot.database import get_db_context
from bot.services.location_service import LocationService
from bot.services.achievements_manager import AchievementsManager
from bot.utils.users import get_or_create_user

ASK_NAME, ASK_DESCRIPTION, ASK_LOCATION, ASK_PHOTO, CONFIRM = range(5)

async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📍 Введи название локации:")
    return ASK_NAME

async def ask_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["loc_name"] = update.message.text.strip()
    await update.message.reply_text("✏️ Напиши краткое описание (или - для пропуска):")
    return ASK_DESCRIPTION

async def ask_coords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    context.user_data["loc_description"] = None if desc == "-" else desc

    kb = ReplyKeyboardMarkup(
        [[KeyboardButton("📡 Отправить геопозицию", request_location=True)]],
        resize_keyboard=True
    )
    await update.message.reply_text(
        "📌 Отправь локацию через кнопку ниже:",
        reply_markup=kb
    )
    return ASK_LOCATION

async def get_coords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.location:
        await update.message.reply_text("⚠️ Это не похоже на геопозицию, попробуй еще раз")
        return ASK_LOCATION

    loc = update.message.location
    context.user_data["latitude"] = loc.latitude
    context.user_data["longitude"] = loc.longitude

    await update.message.reply_text(
        "📷 Отправь фото места (или напиши `готово` чтобы продолжить)",
        reply_markup=ReplyKeyboardMarkup([["готово"]], resize_keyboard=True)
    )
    return ASK_PHOTO

async def collect_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text.lower() == "готово":
        return await confirm(update, context)

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        context.user_data.setdefault("photos", []).append(file_id)
        await update.message.reply_text("Фото добавлено 📸 (ещё или напиши `готово`)")
        return ASK_PHOTO

    await update.message.reply_text("Отправь фото или `готово`")
    return ASK_PHOTO

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data

    msg = (
        f"🧾 **Проверка данных:**\n"
        f"🏷 Название: {d['loc_name']}\n"
        f"✏️ Описание: {d.get('loc_description') or '—'}\n"
        f"🌍 Координаты: {d['latitude']}, {d['longitude']}\n"
        f"📷 Фото: {len(d.get('photos', []))}\n\n"
        f"Напиши `да` для сохранения или `нет` для отмены"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    return CONFIRM

async def save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower() != "да":
        await update.message.reply_text("❌ Добавление отменено")
        return ConversationHandler.END

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
            description=d.get("loc_description")
        )

        for i, file_id in enumerate(d.get("photos", [])):
            LocationService.add_photo(db, loc.id, file_id, order_index=i)

        completed = achievements.apply_event(db, user.id, "location_submitted", 1)

    await update.message.reply_text(
        "🎉 Локация отправлена на модерацию!\n"
        "После одобрения ты получишь баллы 💎"
    )
    if completed:
        await update.message.reply_text(achievements.format_completion_message(completed))
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено ❌")
    context.user_data.clear()
    return ConversationHandler.END

add_location_handler = ConversationHandler(
    entry_points=[
        CommandHandler("add", start_add),
        MessageHandler(filters.Regex("^(➕ Добавить|add)$"), start_add),
    ],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_description)],
        ASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_coords)],
        ASK_LOCATION: [MessageHandler(filters.LOCATION, get_coords)],
        ASK_PHOTO: [
            MessageHandler(filters.PHOTO, collect_photo),
            MessageHandler(filters.TEXT & ~filters.COMMAND, collect_photo),
        ],
        CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, save)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True
)
