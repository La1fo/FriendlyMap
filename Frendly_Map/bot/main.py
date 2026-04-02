#bot/main.py
import logging
from telegram.error import RetryAfter, TelegramError
from telegram.ext import Application, ContextTypes
from .config import settings
from .database import init_db, get_db_context
from .handlers import get_all_handlers
from .services.achievements_manager import AchievementsManager
from .utils.webapp import webapp_url_diagnostics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _on_application_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled telegram update error", exc_info=context.error)


async def _safe_set_my_commands(application: Application) -> None:
    try:
        await application.bot.set_my_commands([
            ("start", "Запустить бота"),
            ("profile", "Мой профиль"),
            ("map", "Открыть карту"),
            ("add", "Добавить локацию"),
            ("leaderboard", "Топ пользователей"),
            ("achievements", "Достижения"),
            ("pending", "Модерация локаций"),
            ("moderation", "Панель модерации"),
            ("faq", "FAQ"),
        ])
    except RetryAfter as exc:
        # setMyCommands is best-effort on startup: Telegram 429 must not block polling startup
        logger.warning(
            "Bot commands update skipped due to Telegram rate limit; continuing startup. retry_after=%s",
            exc.retry_after,
        )
    except TelegramError:
        logger.exception("Bot commands update failed; continuing startup anyway")


async def post_init(application: Application):
    await _safe_set_my_commands(application)
    ok, message = webapp_url_diagnostics()
    if ok:
        logger.info(message)
    else:
        logger.warning(message)

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
