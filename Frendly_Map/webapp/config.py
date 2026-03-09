# webapp/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DB_URL: str = "sqlite:///./friendly_map.db"
    BOT_TOKEN: str = ""
    OSRM_BASE_URL: str = "https://router.project-osrm.org"
    DEFAULT_MAP_LAT: float = 55.751244
    DEFAULT_MAP_LNG: float = 37.618423
    DEFAULT_MAP_ZOOM: int = 11

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
