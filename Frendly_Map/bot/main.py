#bot/main.py
import logging
from telegram import Bot
from telegram.ext import Application
from telegram.error import TelegramError
from .config import settings
from .database import init_db, get_db_context
from .handlers import get_all_handlers
from .services.achievements_manager import AchievementsManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def post_init(application: Application):
    await application.bot.set_my_commands([
        ("start", "Запустить бота"),
        ("profile", "Мой профиль"),
        ("map", "Открыть карту"),
        ("add", "Добавить локацию"),
        ("leaderboard", "Топ пользователей"),
        ("achievements", "Достижения"),
        ("faq", "FAQ"),
        ("support", "Техподдержка"),
        ("moderation", "Панель модерации"),
        ("pending", "Модерация локаций"),
    ])
    init_db()
    with get_db_context() as db:
        AchievementsManager().ensure_definitions(db)
    logger.info("✅ Бот инициализирован")


async def error_handler(update, context):
    logger.exception("Unhandled error: %s", context.error)
    if update and getattr(update, "effective_message", None):
        try:
            await update.effective_message.reply_text("⚠️ Произошла ошибка. Попробуйте позже.")
        except TelegramError:
            logger.exception("Failed to send error message to user.")

def main():
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан. Укажите его в .env или переменных окружения.")
    app = Application.builder()\
        .token(settings.BOT_TOKEN)\
        .post_init(post_init)\
        .build()
    for handler in get_all_handlers():
        app.add_handler(handler)
    app.add_error_handler(error_handler)
    logger.info("🚀 Запуск Friendly Map Bot...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
