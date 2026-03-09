from __future__ import annotations

from urllib.parse import urlparse

from telegram import WebAppInfo

from bot.config import settings


def build_webapp_url(path: str = "/map") -> str:
    base = settings.WEB_APP_URL.strip().rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def is_public_https_webapp_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        return False

    host = (parsed.hostname or "").lower()
    blocked = {"localhost", "127.0.0.1", "0.0.0.0"}
    return host not in blocked


def get_map_web_app_info() -> WebAppInfo:
    return WebAppInfo(url=build_webapp_url("/map"))


def webapp_url_diagnostics() -> tuple[bool, str]:
    url = settings.WEB_APP_URL.strip()
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False, (
            "WEB_APP_URL некорректен: ожидается полный base URL, например "
            "https://example.com"
        )

    if not is_public_https_webapp_url(url):
        return False, (
            "WEB_APP_URL должен быть публичным HTTPS URL для Telegram WebApp "
            f"(текущее значение: {url!r}). Для локальной разработки используйте HTTPS туннель."
        )

    return True, "WEB_APP_URL корректен для Telegram WebApp"
