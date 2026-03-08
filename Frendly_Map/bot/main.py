#bot/main.py
import logging
from telegram.ext import Application, ContextTypes
from .config import settings
from .database import init_db, get_db_context
from .handlers import get_all_handlers
from .services.achievements_manager import AchievementsManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _on_application_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled telegram update error", exc_info=context.error)

async def post_init(application: Application):
    await application.bot.set_my_commands([
        ("start", "Запустить бота"),
        ("profile", "Мой профиль"),
        ("map", "Открыть карту"),
        ("add", "Добавить локацию"),
        ("leaderboard", "Топ пользователей"),
        ("achievements", "Достижения"),
        ("pending", "Модерация локаций"),
        ("moderation", "Панель модерации"),
        ("support", "Поддержка"),
        ("faq", "FAQ"),
    ])
    init_db()
    with get_db_context() as db:
        AchievementsManager().ensure_definitions(db)
    logger.info("✅ Бот инициализирован")

def main():
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан. Укажите его в .env или переменных окружения.")
    app = Application.builder()\
        .token(settings.BOT_TOKEN)\
        .post_init(post_init)\
        .build()
    for handler in get_all_handlers():
        app.add_handler(handler)
    app.add_error_handler(_on_application_error)
    logger.info("🚀 Запуск Friendly Map Bot...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
