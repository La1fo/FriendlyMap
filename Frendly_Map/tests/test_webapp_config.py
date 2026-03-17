import pytest

from webapp.config import Settings


def test_rejects_wildcard_origins():
    with pytest.raises(ValueError):
        Settings(WEBAPP_ALLOWED_ORIGINS="*")


def test_rejects_wildcard_methods_with_credentials():
    with pytest.raises(ValueError):
        Settings(WEBAPP_ALLOWED_METHODS="*")


def test_rejects_wildcard_headers_with_credentials():
    with pytest.raises(ValueError):
        Settings(WEBAPP_ALLOWED_HEADERS="*")


def test_parses_allowed_lists():
    cfg = Settings(
        WEBAPP_ALLOWED_ORIGINS="https://example.com, http://localhost:8000",
        WEBAPP_ALLOWED_METHODS="GET, POST, OPTIONS",
        WEBAPP_ALLOWED_HEADERS="Authorization, Content-Type",
    )
    assert cfg.allowed_origins == ["https://example.com", "http://localhost:8000"]
    assert cfg.allowed_methods == ["GET", "POST", "OPTIONS"]
    assert cfg.allowed_headers == ["Authorization", "Content-Type"]
