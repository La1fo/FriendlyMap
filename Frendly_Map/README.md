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


## Telegram Mini App / Web App запуск

Для кнопки **КАРТА** в Telegram нужен **публичный HTTPS URL** в `WEB_APP_URL`.

### Локальная разработка
1. Запустите webapp локально: `python -m webapp.main` (например, на `http://localhost:8000`).
2. Поднимите HTTPS-туннель (ngrok, cloudflared, pinggy и т.п.) на локальный порт 8000.
3. Установите `WEB_APP_URL` в `.env` как публичный HTTPS base URL туннеля, например: `https://<your-tunnel>.example`.
4. Запустите бота: `python -m bot.main`.

> `http://localhost:8000` можно использовать для браузерной проверки, но Telegram WebApp не откроет localhost у конечного пользователя.
