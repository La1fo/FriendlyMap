# Friendly Map

Friendly Map — Telegram-бот и веб-приложение с картой дружественных мест.

## Быстрый старт (локально)

1. Установите зависимости:

```bash
pip install -r requirements.txt
```

2. Создайте файл `.env` (можно взять из примера `.env.example`) и заполните переменные.

3. Запустите БД (если используете PostgreSQL) и сервисы:

```bash
python init_db.py
python -m webapp.main
python -m bot.main
```

## Запуск через Docker Compose

```bash
docker compose up --build
```

Это поднимет:
- PostgreSQL
- веб-приложение на `http://localhost:8000/map`
- Telegram-бота

## Переменные окружения

- `BOT_TOKEN` — токен Telegram-бота (обязательно)
- `DB_URL` — строка подключения к БД (по умолчанию `sqlite:///./friendly_map.db`)
- `WEB_APP_URL` — URL веб-приложения (по умолчанию `http://localhost:8000`)
- `ADMIN_IDS` — список ID администраторов через запятую
- `SEED_SAMPLE_DATA` — добавлять тестовых пользователей для лидерборда (по умолчанию `false`)
