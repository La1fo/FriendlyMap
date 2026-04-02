# bot/config.py
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str = ""

    # База данных
    DB_URL: str = "sqlite:///./friendly_map.db"

    # Администраторы (через запятую)
    ADMIN_IDS: str = ""

    # Web App (для Telegram нужен публичный HTTPS base URL; localhost только для backend-локалки)
    WEB_APP_URL: str = "http://localhost:8000"

    # Seed sample users for leaderboard (dev only)
    SEED_SAMPLE_DATA: bool = False

    # Преобразуем ADMIN_IDS в список чисел
    @property
    def ADMIN_IDS_LIST(self) -> List[int]:
        if self.ADMIN_IDS.strip():
            return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]
        return []

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Глобальный экземпляр
settings = Settings()


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if settings.DB_URL.startswith("sqlite:///./"):
    rel_path = settings.DB_URL.removeprefix("sqlite:///./")
    settings.DB_URL = f"sqlite:///{(_PROJECT_ROOT / rel_path).resolve()}"
