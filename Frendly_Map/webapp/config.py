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
    WEBAPP_ALLOWED_METHODS: str = "GET,POST,OPTIONS"
    WEBAPP_ALLOWED_HEADERS: str = "Authorization,Content-Type,X-Requested-With"
    ADMIN_IDS: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.WEBAPP_ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_methods(self) -> list[str]:
        return [m.strip().upper() for m in self.WEBAPP_ALLOWED_METHODS.split(",") if m.strip()]

    @property
    def allowed_headers(self) -> list[str]:
        return [h.strip() for h in self.WEBAPP_ALLOWED_HEADERS.split(",") if h.strip()]

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

    @field_validator("WEBAPP_ALLOWED_METHODS")
    @classmethod
    def validate_methods(cls, value: str) -> str:
        methods = [m.strip().upper() for m in value.split(",") if m.strip()]
        if not methods:
            raise ValueError("WEBAPP_ALLOWED_METHODS must contain at least one HTTP method")
        if "*" in methods:
            raise ValueError("Wildcard '*' is not allowed for WEBAPP_ALLOWED_METHODS when credentials are enabled")
        return value

    @field_validator("WEBAPP_ALLOWED_HEADERS")
    @classmethod
    def validate_headers(cls, value: str) -> str:
        headers = [h.strip() for h in value.split(",") if h.strip()]
        if not headers:
            raise ValueError("WEBAPP_ALLOWED_HEADERS must contain at least one header")
        if "*" in headers:
            raise ValueError("Wildcard '*' is not allowed for WEBAPP_ALLOWED_HEADERS when credentials are enabled")
        return value


settings = Settings()


def is_admin_id(user_id: int) -> bool:
    return str(user_id) in settings.ADMIN_IDS.split(",")


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if settings.DB_URL.startswith("sqlite:///./"):
    rel_path = settings.DB_URL.removeprefix("sqlite:///./")
    settings.DB_URL = f"sqlite:///{(_PROJECT_ROOT / rel_path).resolve()}"
