from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

SCHEMA_VERSION_TABLE = "schema_version"
CURRENT_SCHEMA_VERSION = 2


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
            conn.execute(text("UPDATE users SET total_gp = COALESCE(total_gp, 0) + CASE WHEN total_gp = 0 THEN COALESCE(pts, 0) ELSE 0 END"))
        elif "points" in columns:
            conn.execute(text("UPDATE users SET total_gp = COALESCE(total_gp, 0) + CASE WHEN total_gp = 0 THEN COALESCE(points, 0) ELSE 0 END"))

        # keep compatibility mirror for old code paths during transition
        if "pts" in columns:
            conn.execute(text("UPDATE users SET pts = total_gp WHERE COALESCE(pts, -1) <> total_gp"))


def _create_site_views(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP VIEW IF EXISTS site_public_locations"))
        conn.execute(text("DROP VIEW IF EXISTS site_public_users"))
        conn.execute(text("DROP VIEW IF EXISTS site_leaderboard"))
        conn.execute(text("DROP VIEW IF EXISTS site_achievements_overview"))

        conn.execute(
            text(
                """
                CREATE VIEW site_public_users AS
                SELECT
                    u.id AS user_id,
                    COALESCE(NULLIF(u.username, ''), u.first_name, 'Пользователь') AS username,
                    u.telegram_id AS telegram_id,
                    u.total_gp AS total_gp,
                    (CAST(u.total_gp / 100 AS INTEGER) + 1) AS rank_level,
                    (u.total_gp % 100) AS gp_in_rank,
                    ('Ранг ' || ((CAST(u.total_gp / 100 AS INTEGER) + 1))) AS rank_name,
                    u.approved_locations AS approved_locations
                FROM users u
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE VIEW site_public_locations AS
                SELECT
                    l.id,
                    l.name,
                    l.description,
                    l.latitude,
                    l.longitude,
                    l.address,
                    l.created_at,
                    u.id AS author_id,
                    COALESCE(NULLIF(u.username, ''), u.first_name, 'Пользователь') AS author_name
                FROM locations l
                JOIN users u ON u.id = l.user_id
                WHERE l.status = 'approved'
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE VIEW site_leaderboard AS
                SELECT
                    u.id AS user_id,
                    COALESCE(NULLIF(u.username, ''), u.first_name, 'Пользователь') AS username,
                    u.total_gp AS total_gp,
                    (CAST(u.total_gp / 100 AS INTEGER) + 1) AS rank_level,
                    (u.total_gp % 100) AS gp_in_rank,
                    ('Ранг ' || ((CAST(u.total_gp / 100 AS INTEGER) + 1))) AS rank_name,
                    ROW_NUMBER() OVER (ORDER BY u.total_gp DESC, u.id ASC) AS position
                FROM users u
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
                    a.type,
                    COUNT(ua.id) FILTER (WHERE ua.is_completed = TRUE) AS completed_count
                FROM achievements a
                LEFT JOIN user_achievements ua ON ua.achievement_id = a.id
                GROUP BY a.id, a.code, a.name, a.type
                """
            )
        )


def run_migrations(engine: Engine) -> None:
    current = get_schema_version(engine)
    if current >= CURRENT_SCHEMA_VERSION:
        return

    _ensure_total_gp_column(engine)
    _create_site_views(engine)

    with engine.begin() as conn:
        conn.execute(text(f"INSERT INTO {SCHEMA_VERSION_TABLE}(version) VALUES (:version)"), {"version": CURRENT_SCHEMA_VERSION})


def assert_schema_version(engine: Engine) -> None:
    current = get_schema_version(engine)
    if current < CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema version {current} is older than required {CURRENT_SCHEMA_VERSION}. Run migrations before startup."
        )
