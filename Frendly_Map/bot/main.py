#bot/main.py
import logging
from telegram import Bot
from telegram.ext import Application
from .config import settings
from .database import init_db, get_db_session
from .handlers import get_all_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def post_init(application: Application):
    await application.bot.set_my_commands([
        ("start", "Запустить бота"),
        ("profile", "Мой профиль"),
        ("map", "Открыть карту"),
        ("add", "Добавить локацию"),
    ])
    init_db()
    logger.info("✅ Бот инициализирован")

def main():
    app = Application.builder()\
        .token(settings.BOT_TOKEN)\
        .post_init(post_init)\
        .build()
    for handler in get_all_handlers():
        app.add_handler(handler)
    logger.info("🚀 Запуск Friendly Map Bot...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
