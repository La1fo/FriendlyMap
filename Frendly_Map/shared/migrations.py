from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

SCHEMA_VERSION_TABLE = "schema_version"
CURRENT_SCHEMA_VERSION = 4


def _ensure_schema_version_table(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA_VERSION_TABLE} (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                )
                """
            )
        )


def get_schema_version(engine: Engine) -> int:
    _ensure_schema_version_table(engine)
    with engine.begin() as conn:
        row = conn.execute(text(f"SELECT COALESCE(MAX(version), 0) FROM {SCHEMA_VERSION_TABLE}")).scalar()
        return int(row or 0)


def _ensure_total_gp_column(engine: Engine) -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        columns = {c["name"] for c in inspector.get_columns("users")}

        if "total_gp" not in columns:
            conn.execute(text('ALTER TABLE users ADD COLUMN total_gp INTEGER NOT NULL DEFAULT 0'))

        # Backfill canonical total_gp from historical fields (priority: pts -> points -> 0)
        if "pts" in columns:
            conn.execute(
                text(
                    "UPDATE users SET total_gp = CASE WHEN total_gp = 0 THEN COALESCE(pts, 0) ELSE total_gp END"
                )
            )
        elif "points" in columns:
            conn.execute(
                text(
                    "UPDATE users SET total_gp = CASE WHEN total_gp = 0 THEN COALESCE(points, 0) ELSE total_gp END"
                )
            )


def _create_site_views(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP VIEW IF EXISTS site_public_locations"))
        conn.execute(text("DROP VIEW IF EXISTS site_public_users"))
        conn.execute(text("DROP VIEW IF EXISTS site_leaderboard"))
        conn.execute(text("DROP VIEW IF EXISTS site_achievements_overview"))
        conn.execute(text("DROP VIEW IF EXISTS site_auth_users"))

        conn.execute(
            text(
                """
                CREATE VIEW site_public_users AS
                WITH ranked_users AS (
                    SELECT
                        u.*,
                        ROW_NUMBER() OVER (ORDER BY u.total_gp DESC, u.id ASC) AS position
                    FROM users u
                )
                SELECT
                    u.id AS user_id,
                    COALESCE(NULLIF(u.username, ''), u.first_name, 'Пользователь') AS username,
                    u.telegram_id AS telegram_id,
                    u.total_gp AS total_gp,
                    CASE
                        WHEN u.total_gp >= 1300 AND u.position <= 10 THEN 11
                        WHEN u.total_gp >= 900 THEN 10
                        ELSE (CAST(u.total_gp / 100 AS INTEGER) + 1)
                    END AS rank_level,
                    CASE
                        WHEN u.total_gp >= 1300 AND u.position <= 10 THEN 400
                        WHEN u.total_gp >= 900 THEN MIN(u.total_gp - 900, 400)
                        ELSE (u.total_gp % 100)
                    END AS gp_in_rank,
                    CASE
                        WHEN u.total_gp >= 1300 AND u.position <= 10 THEN '⭐ Мастер-картограф'
                        WHEN u.total_gp >= 900 THEN '🟣 Картограф'
                        WHEN u.total_gp >= 800 THEN '🟡 Первооткрыватель 3'
                        WHEN u.total_gp >= 700 THEN '🟡 Первооткрыватель 2'
                        WHEN u.total_gp >= 600 THEN '🟡 Первооткрыватель 1'
                        WHEN u.total_gp >= 500 THEN '🔵 Путешественник 3'
                        WHEN u.total_gp >= 400 THEN '🔵 Путешественник 2'
                        WHEN u.total_gp >= 300 THEN '🔵 Путешественник 1'
                        WHEN u.total_gp >= 200 THEN '🟢 Исследователь 3'
                        WHEN u.total_gp >= 100 THEN '🟢 Исследователь 2'
                        ELSE '🟢 Исследователь 1'
                    END AS rank_name,
                    u.approved_locations AS approved_locations
                FROM ranked_users u
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE VIEW site_leaderboard AS
                WITH ranked_users AS (
                    SELECT
                        u.*,
                        ROW_NUMBER() OVER (ORDER BY u.total_gp DESC, u.id ASC) AS position
                    FROM users u
                )
                SELECT
                    u.id AS user_id,
                    COALESCE(NULLIF(u.username, ''), u.first_name, 'Пользователь') AS username,
                    u.total_gp AS total_gp,
                    CASE
                        WHEN u.total_gp >= 1300 AND u.position <= 10 THEN 11
                        WHEN u.total_gp >= 900 THEN 10
                        ELSE (CAST(u.total_gp / 100 AS INTEGER) + 1)
                    END AS rank_level,
                    CASE
                        WHEN u.total_gp >= 1300 AND u.position <= 10 THEN 400
                        WHEN u.total_gp >= 900 THEN MIN(u.total_gp - 900, 400)
                        ELSE (u.total_gp % 100)
                    END AS gp_in_rank,
                    CASE
                        WHEN u.total_gp >= 1300 AND u.position <= 10 THEN '⭐ Мастер-картограф'
                        WHEN u.total_gp >= 900 THEN '🟣 Картограф'
                        WHEN u.total_gp >= 800 THEN '🟡 Первооткрыватель 3'
                        WHEN u.total_gp >= 700 THEN '🟡 Первооткрыватель 2'
                        WHEN u.total_gp >= 600 THEN '🟡 Первооткрыватель 1'
                        WHEN u.total_gp >= 500 THEN '🔵 Путешественник 3'
                        WHEN u.total_gp >= 400 THEN '🔵 Путешественник 2'
                        WHEN u.total_gp >= 300 THEN '🔵 Путешественник 1'
                        WHEN u.total_gp >= 200 THEN '🟢 Исследователь 3'
                        WHEN u.total_gp >= 100 THEN '🟢 Исследователь 2'
                        ELSE '🟢 Исследователь 1'
                    END AS rank_name,
                    u.position AS position
                FROM ranked_users u
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE VIEW site_public_locations AS
                SELECT
                    l.id AS location_id,
                    l.user_id AS user_id
                FROM locations l
                WHERE l.status = 'approved'
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE VIEW site_achievements_overview AS
                SELECT
                    a.id AS achievement_id,
                    a.code,
                    a.name,
                    a.description,
                    COUNT(ua.id) FILTER (WHERE ua.is_completed = TRUE) AS completed_count,
                    a.is_seasonal AS is_seasonal
                FROM achievements a
                LEFT JOIN user_achievements ua ON ua.achievement_id = a.id
                GROUP BY a.id, a.code, a.name, a.description, a.is_seasonal
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE VIEW site_auth_users AS
                SELECT
                    u.id AS user_id,
                    COALESCE(NULLIF(u.username, ''), u.first_name, 'Пользователь') AS username,
                    u.telegram_id AS telegram_id,
                    u.email AS email,
                    u.password_hash AS hashed_password
                FROM users u
                """
            )
        )


def run_migrations(engine: Engine) -> None:
    current = get_schema_version(engine)

    # Keep migration runner idempotent and self-healing: always re-apply
    # non-destructive schema/view guarantees required by writer-side services.
    _ensure_total_gp_column(engine)
    _create_site_views(engine)

    if current >= CURRENT_SCHEMA_VERSION:
        return

    with engine.begin() as conn:
        conn.execute(
            text(f"INSERT INTO {SCHEMA_VERSION_TABLE}(version) VALUES (:version)"),
            {"version": CURRENT_SCHEMA_VERSION},
        )


def assert_schema_version(engine: Engine) -> None:
    current = get_schema_version(engine)
    if current < CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema version {current} is older than required {CURRENT_SCHEMA_VERSION}. Run migrations before startup."
        )
