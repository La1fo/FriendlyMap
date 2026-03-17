import pytest

from webapp.config import Settings


def test_rejects_wildcard_origins():
    with pytest.raises(ValueError):
        Settings(WEBAPP_ALLOWED_ORIGINS="*")


def test_parses_allowed_origins_list():
    cfg = Settings(WEBAPP_ALLOWED_ORIGINS="https://example.com, http://localhost:8000")
    assert cfg.allowed_origins == ["https://example.com", "http://localhost:8000"]
