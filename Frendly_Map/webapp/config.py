# webapp/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DB_URL: str = "sqlite:///./friendly_map.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
