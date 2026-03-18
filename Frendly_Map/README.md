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

### Важно для Docker
- В `docker-compose.yml` webapp и bot автоматически используют `DB_URL` c хостом `db` (если `DB_URL` не задан во внешней среде).
- Для открытия WebApp в Telegram укажите публичный HTTPS в `WEB_APP_URL` (например URL туннеля).
- Если `WEB_APP_URL` не указан, по умолчанию используется `http://localhost:8000` (удобно только для локальной проверки в браузере, не в Telegram-клиенте).

## Переменные окружения

- `BOT_TOKEN` — токен Telegram-бота (обязательно)
- `DB_URL` — строка подключения к БД (по умолчанию `sqlite:///./friendly_map.db`)
- `WEB_APP_URL` — URL веб-приложения (по умолчанию `http://localhost:8000`)
- `ADMIN_IDS` — список ID администраторов через запятую
- `SEED_SAMPLE_DATA` — добавлять тестовых пользователей для лидерборда (по умолчанию `false`)
- `WEBAPP_ALLOWED_ORIGINS` — список разрешённых CORS origin через запятую (например `https://app.example.com,https://miniapp.example.com`)
- `WEBAPP_ALLOWED_METHODS` — явный список CORS методов (по умолчанию `GET,POST,OPTIONS`)
- `WEBAPP_ALLOWED_HEADERS` — явный список CORS заголовков (по умолчанию `Authorization,Content-Type,X-Requested-With`)


## Telegram Mini App / Web App запуск

Для кнопки **КАРТА** в Telegram нужен **публичный HTTPS URL** в `WEB_APP_URL`.

### Локальная разработка
1. Запустите webapp локально: `python -m webapp.main` (например, на `http://localhost:8000`).
2. Поднимите HTTPS-туннель (ngrok, cloudflared, pinggy и т.п.) на локальный порт 8000.
3. Установите `WEB_APP_URL` в `.env` как публичный HTTPS base URL туннеля, например: `https://<your-tunnel>.example`.
4. Запустите бота: `python -m bot.main`.

> `http://localhost:8000` можно использовать для браузерной проверки, но Telegram WebApp не откроет localhost у конечного пользователя.

## Каноническая схема БД (shared)

Бот и webapp используют общий контракт ORM из `shared/models` и один `DB_URL`.

Базовые доменные таблицы:
- `users`
- `locations`
- `photos`
- `tags`
- `location_tags`
- `achievements`
- `seasons`
- `user_achievements`
- `webapp_picks`

Технические таблицы бота (writer-side):
- `faq_entries`
- `support_tickets`
- `support_messages`
- `support_sessions`
- `shop_items`

## Миграции и версия схемы

В проекте используется встроенный migration runner (`shared/migrations.py`) со схемной версией:
- таблица `schema_version`
- текущая версия проверяется на старте bot/webapp
- при `init_db()` применяются миграции и создаются SQL view для read-only сайта

### Как запустить миграции

Миграции запускаются автоматически при старте приложения (`init_db()`).
При ручной инициализации можно использовать обычный старт:

```bash
python -m webapp.main
python -m bot.main
```

## Read-only слой для отдельного сайта

Для сайта добавлены SQL VIEW (бот в них не пишет):
- `site_leaderboard`
- `site_public_users`
- `site_public_locations`
- `site_achievements_overview`
- `site_auth_users`

Финальный контракт VIEW:

- `site_leaderboard`:
  - `user_id`
  - `username`
  - `total_gp`
  - `rank_level`
  - `gp_in_rank`
  - `rank_name`
  - `position`

- `site_public_users`:
  - `user_id`
  - `username`
  - `telegram_id`
  - `total_gp`
  - `rank_level`
  - `gp_in_rank`
  - `rank_name`
  - `approved_locations`

- `site_public_locations`:
  - `location_id`
  - `user_id`

- `site_achievements_overview`:
  - `achievement_id`
  - `code`
  - `name`
  - `description`
  - `completed_count`
  - `is_seasonal`

- `site_auth_users`:
  - `user_id`
  - `username`
  - `telegram_id`
  - `email`
  - `hashed_password`

Сайт должен использовать read-only DB роль (`SELECT` only) на этих view и нужных публичных таблицах.

## Ranking system contract

- Бот и webapp — writer-side сервисы общей БД.
- Канонический источник истины для рангов: `users.total_gp`.
- Изменение `total_gp` (начисление GP) выполняется writer-side логикой бота.
- Сайт читает ранги из read-only view (`site_public_users`, `site_leaderboard`).
- Поля `rank_level`, `gp_in_rank`, `rank_name` вычисляются, а не хранятся как канонические колонки.
- `users.points` — отдельная валюта (монеты) и не участвует в расчёте ранга GP.

### Migration / backfill plan

1. `schema_version` хранит применённые версии миграции.
2. На миграции рангов:
   - добавить `users.total_gp`, если поля нет;
   - выполнить backfill `total_gp` из legacy `pts`, fallback из `points` только когда `total_gp = 0`.
3. Пересоздать все обязательные `site_*` VIEW.
4. После этого ранговая логика writer-side использует только `total_gp`.

Формула:

- `rank_level = floor(total_gp / 100) + 1`
- `gp_in_rank = total_gp % 100`
- `rank_name = "Ранг {rank_level}"`

Примеры:

- `total_gp=99` → `rank_level=1`, `gp_in_rank=99`
- `total_gp=102` → `rank_level=2`, `gp_in_rank=2`

## Release verification checklist (writer-side)

- [ ] Бот и webapp запущены как writer-side сервисы общей БД (`DB_URL` общий).
- [ ] Сайт подключён только с read-only правами и читает через `site_*` VIEW.
- [ ] Ранговый источник истины только `users.total_gp` (runtime не использует `pts`).
- [ ] `users.points` используется только как отдельная валюта (монеты), не как GP.
- [ ] Все 5 `site_*` VIEW существуют и совпадают с контрактом колонок из этого README.
- [ ] Формула ранга единая: `rank_level=floor(total_gp/100)+1`, `gp_in_rank=total_gp%100`, `rank_name="Ранг {rank_level}"`.
- [ ] Профиль/лидерборд/API показывают:
  - `Ранг N`
  - `GP в текущем ранге: X/100`
  - `Общий GP: Y`
  - монеты отдельно (если включены в UI).
- [ ] Telegram Mini App `init_data` валидация включена и отклоняет невалидную подпись.
- [ ] CORS конфиг задан явно (`WEBAPP_ALLOWED_ORIGINS/METHODS/HEADERS`) и не использует `*` при credentials.
- [ ] Прогнан набор тестов release-уровня (`pytest`) без падений.
