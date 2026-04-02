import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

from telegram.error import RetryAfter, TelegramError

from bot import main as bot_main


class _FakeBot:
    def __init__(self, exc: Exception | None = None):
        self.exc = exc
        self.called = False

    async def set_my_commands(self, commands):
        self.called = True
        if self.exc:
            raise self.exc


def test_post_init_continues_after_retry_after(monkeypatch, caplog):
    bot = _FakeBot(RetryAfter(5))
    calls: list[str] = []

    monkeypatch.setattr(bot_main, "webapp_url_diagnostics", lambda: (True, "webapp ok"))
    monkeypatch.setattr(bot_main, "init_db", lambda: calls.append("init_db"))

    @contextmanager
    def fake_db_context():
        calls.append("db_context")
        yield "db"

    monkeypatch.setattr(bot_main, "get_db_context", fake_db_context)
    monkeypatch.setattr(
        bot_main,
        "AchievementsManager",
        lambda: SimpleNamespace(ensure_definitions=lambda db: calls.append(f"ensure:{db}")),
    )

    asyncio.run(bot_main.post_init(SimpleNamespace(bot=bot)))

    assert bot.called is True
    assert calls == ["init_db", "db_context", "ensure:db"]
    assert "rate limit" in caplog.text


def test_post_init_continues_after_generic_telegram_error(monkeypatch, caplog):
    bot = _FakeBot(TelegramError("boom"))
    calls: list[str] = []

    monkeypatch.setattr(bot_main, "webapp_url_diagnostics", lambda: (False, "webapp warning"))
    monkeypatch.setattr(bot_main, "init_db", lambda: calls.append("init_db"))

    @contextmanager
    def fake_db_context():
        calls.append("db_context")
        yield "db"

    monkeypatch.setattr(bot_main, "get_db_context", fake_db_context)
    monkeypatch.setattr(
        bot_main,
        "AchievementsManager",
        lambda: SimpleNamespace(ensure_definitions=lambda db: calls.append(f"ensure:{db}")),
    )

    asyncio.run(bot_main.post_init(SimpleNamespace(bot=bot)))

    assert bot.called is True
    assert calls == ["init_db", "db_context", "ensure:db"]
    assert "continuing startup" in caplog.text
