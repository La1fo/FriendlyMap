from datetime import datetime, timedelta, timezone

from bot.services.achievements_manager import AchievementsManager
from shared.db import create_db_engine, create_session_factory, init_schema
from shared.models.achievement import Achievement
from shared.models.location import Location
from shared.models.location_tag import LocationTag
from shared.models.season import Season
from shared.models.tag import Tag
from shared.models.user import User
from shared.models.user_achievement import UserAchievement


def _setup_db(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'achievements.db'}")
    SessionLocal = create_session_factory(engine)
    init_schema(engine)
    return SessionLocal


def _add_location(db, user_id: int, status: str, when: datetime):
    loc = Location(
        user_id=user_id,
        name=f"L-{status}-{when.timestamp()}",
        latitude=10.0,
        longitude=20.0,
        status=status,
        moderated_at=when,
        created_at=when,
    )
    db.add(loc)
    db.flush()
    return loc


def test_permanent_achievements_and_idempotency(tmp_path):
    SessionLocal = _setup_db(tmp_path)
    manager = AchievementsManager()
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        user = User(id=10, telegram_id=10, username="u10", points=0, total_gp=0)
        db.add(user)
        for idx in range(1, 21):
            db.add(Tag(id=idx, name=f"tag{idx}", category="cat"))
        db.commit()

        for i in range(100):
            ts = now - timedelta(days=i // 10, hours=i % 5)
            loc = _add_location(db, user.id, "approved", ts)
            if i < 20:
                db.add(LocationTag(location_id=loc.id, tag_id=i + 1))
        _add_location(db, user.id, "rejected", now - timedelta(days=1, hours=1))
        for j in range(5):
            _add_location(db, user.id, "approved", now - timedelta(hours=5 - j))
        user.points = 5000
        db.commit()

        first = manager.apply_event(db, user.id, "location_approved", event_key="approve:bulk")
        second = manager.apply_event(db, user.id, "location_approved", event_key="approve:bulk")
        codes_first = {a.code for a in first}
        assert second == []
        assert {
            "first_approved_location",
            "use_20_unique_tags",
            "active_10_days",
            "earn_1000_coins",
            "clean_streak_5",
            "approve_5_in_24h",
            "approved_25_locations",
            "approved_50_locations",
            "approved_100_locations",
            "earn_5000_coins",
        } <= codes_first


def test_streak_resets_after_reject(tmp_path):
    SessionLocal = _setup_db(tmp_path)
    manager = AchievementsManager()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        user = User(id=20, telegram_id=20, username="u20", points=0, total_gp=0)
        db.add(user)
        db.commit()
        for i in range(4):
            _add_location(db, user.id, "approved", now - timedelta(hours=10 - i))
        _add_location(db, user.id, "rejected", now - timedelta(hours=5))
        for i in range(4):
            _add_location(db, user.id, "approved", now - timedelta(hours=4 - i))
        db.commit()
        manager.apply_event(db, user.id, "location_approved", event_key="streak-check")
        achievement = db.query(Achievement).filter(Achievement.code == "clean_streak_5").first()
        ua = db.query(UserAchievement).filter(UserAchievement.user_id == user.id, UserAchievement.achievement_id == achievement.id).first()
        assert ua.progress == 4
        assert ua.is_completed is False


def test_seasonal_achievements_isolation_and_finalization(tmp_path):
    SessionLocal = _setup_db(tmp_path)
    manager = AchievementsManager()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        user = User(id=30, telegram_id=30, username="u30", points=0, total_gp=0)
        db.add(user)
        db.commit()

        season = manager.get_current_season(db, now=now)
        start = season.start_date.replace(tzinfo=timezone.utc)
        for i in range(5):
            _add_location(db, user.id, "approved", start + timedelta(hours=i * 6))
        _add_location(db, user.id, "rejected", start + timedelta(hours=25))
        for i in range(5):
            _add_location(db, user.id, "approved", start + timedelta(hours=30 + i))
        db.commit()

        manager.apply_event(db, user.id, "coins_earned", 1000, event_key="season:coins:1")
        manager.apply_event(db, user.id, "coins_earned", 1000, event_key="season:coins:1")
        manager.apply_event(db, user.id, "location_approved", event_key="season:approve")
        manager.apply_season_finalization(db, season.id, [user.id, 999, 998])

        season_codes = {
            "season_add_5_locations",
            "season_add_3_in_24h",
            "season_add_5_in_2_days",
            "season_first_3_days",
            "season_clean_streak_5",
            "season_earn_1000_coins",
            "season_rank_1",
            "season_top_3",
            "season_top_10",
        }
        completed_codes = {
            a.code
            for a in db.query(Achievement)
            .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
            .filter(UserAchievement.user_id == user.id, UserAchievement.season_id == season.id, UserAchievement.is_completed.is_(True))
            .all()
        }
        assert season_codes <= completed_codes

        next_season = Season(
            key="2099-Q1",
            start_date=start + timedelta(days=120),
            end_date=start + timedelta(days=210),
        )
        db.add(next_season)
        db.commit()
        next_entries = db.query(UserAchievement).filter(UserAchievement.user_id == user.id, UserAchievement.season_id == next_season.id).all()
        assert next_entries == []
