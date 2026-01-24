# bot/config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str = ""

    # База данных
    DB_URL: str = "sqlite:///./friendly_map.db"

    # Администраторы (через запятую)
    ADMIN_IDS: str = ""

    # Web App
    WEB_APP_URL: str = "http://localhost:8000"

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
