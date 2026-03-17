from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_URL: str = "sqlite:///./friendly_map.db"
    BOT_TOKEN: str = ""
    OSRM_BASE_URL: str = "https://router.project-osrm.org"
    DEFAULT_MAP_LAT: float = 55.751244
    DEFAULT_MAP_LNG: float = 37.618423
    DEFAULT_MAP_ZOOM: int = 11
    WEBAPP_ALLOWED_ORIGINS: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.WEBAPP_ALLOWED_ORIGINS.split(",") if o.strip()]

    @field_validator("WEBAPP_ALLOWED_ORIGINS")
    @classmethod
    def validate_origins(cls, value: str) -> str:
        origins = [o.strip() for o in value.split(",") if o.strip()]
        if not origins:
            raise ValueError("WEBAPP_ALLOWED_ORIGINS must contain at least one origin")
        if "*" in origins:
            raise ValueError("Wildcard '*' is not allowed for WEBAPP_ALLOWED_ORIGINS when credentials are enabled")
        for origin in origins:
            if not (origin.startswith("https://") or origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1")):
                raise ValueError(f"Unsafe origin '{origin}'. Use https:// origin or localhost for dev")
        return value


settings = Settings()


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if settings.DB_URL.startswith("sqlite:///./"):
    rel_path = settings.DB_URL.removeprefix("sqlite:///./")
    settings.DB_URL = f"sqlite:///{(_PROJECT_ROOT / rel_path).resolve()}"
