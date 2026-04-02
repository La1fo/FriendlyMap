import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from bot.models.achievement import Achievement
from bot.models.location import Location
from bot.models.location_tag import LocationTag
from bot.models.season import Season
from bot.models.user import User
from bot.models.user_achievement import UserAchievement
from shared.models.coin_transaction import CoinTransaction


@dataclass(frozen=True)
class AchievementDefinition:
    code: str
    name: str
    description: str
    icon: str
    type: str  # standard | ranked
    target: int
    points_reward: int
    pts_reward: int = 0

    def conditions_json(self) -> str:
        return json.dumps({"target": self.target}, ensure_ascii=False)


DEFINITIONS: List[AchievementDefinition] = [
    AchievementDefinition("first_approved_location", "Первый успех", "Первая одобренная локация", "✅", "standard", 1, 25),
    AchievementDefinition("use_20_unique_tags", "Коллекционер тегов", "Используй 20 уникальных тегов в одобренных локациях", "🏷️", "standard", 20, 40),
    AchievementDefinition("active_10_days", "10 активных дней", "Иметь одобренные локации в 10 разных днях", "📅", "standard", 10, 50),
    AchievementDefinition("earn_1000_coins", "Копилка 1000", "Накопить 1000 монет", "💰", "standard", 1000, 35),
    AchievementDefinition("clean_streak_5", "Чистая серия", "5 одобрений подряд без отклонений", "🔥", "standard", 5, 45),
    AchievementDefinition("approve_5_in_24h", "Быстрый автор", "5 одобрений за 24 часа", "⚡", "standard", 5, 45),
    AchievementDefinition("approved_25_locations", "25 одобренных локаций", "Получить 25 одобренных локаций", "🥉", "standard", 25, 60),
    AchievementDefinition("approved_50_locations", "50 одобренных локаций", "Получить 50 одобренных локаций", "🥈", "standard", 50, 90),
    AchievementDefinition("approved_100_locations", "100 одобренных локаций", "Получить 100 одобренных локаций", "🥇", "standard", 100, 150),
    AchievementDefinition("earn_5000_coins", "Копилка 5000", "Накопить 5000 монет", "🏦", "standard", 5000, 120),
    AchievementDefinition("season_rank_1", "Чемпион сезона", "Закончить сезон на 1 месте", "👑", "ranked", 1, 120, 40),
    AchievementDefinition("season_add_5_locations", "Сезон: 5 локаций", "Получить 5 одобренных локаций за сезон", "🧭", "ranked", 5, 50, 20),
    AchievementDefinition("season_add_3_in_24h", "Сезонный спринт", "Получить 3 одобренные локации за 24 часа в сезоне", "🚀", "ranked", 3, 45, 15),
    AchievementDefinition("season_top_10", "Топ-10 сезона", "Закончить сезон в топ-10", "🏅", "ranked", 10, 80, 25),
    AchievementDefinition("season_first_3_days", "Ранний старт", "Получить первую одобренную локацию в первые 3 дня сезона", "🌅", "ranked", 1, 45, 15),
    AchievementDefinition("season_clean_streak_5", "Сезонная серия", "5 одобрений подряд в сезоне", "📈", "ranked", 5, 60, 20),
    AchievementDefinition("season_top_3", "Топ-3 сезона", "Закончить сезон в топ-3", "🥇", "ranked", 3, 100, 35),
    AchievementDefinition("season_add_5_in_2_days", "Марафон 48ч", "Получить 5 одобренных локаций за 48 часов в сезоне", "⏱️", "ranked", 5, 70, 20),
    AchievementDefinition("season_earn_1000_coins", "Сезонная монетизация", "Заработать 1000 монет за сезон", "🪙", "ranked", 1000, 60, 15),
]


class AchievementsManager:
    def ensure_definitions(self, db: Session) -> None:
        valid_codes = {definition.code for definition in DEFINITIONS}

        for definition in DEFINITIONS:
            achievement = db.query(Achievement).filter(Achievement.code == definition.code).first()
            if not achievement:
                achievement = Achievement(code=definition.code)
                db.add(achievement)
            achievement.name = definition.name
            achievement.description = definition.description
            achievement.icon = definition.icon
            achievement.points_reward = definition.points_reward
            achievement.pts_reward = definition.pts_reward
            achievement.type = definition.type
            achievement.is_seasonal = definition.type == "ranked"
            achievement.conditions = definition.conditions_json()

        legacy = db.query(Achievement).filter(~Achievement.code.in_(valid_codes)).all()
        for achievement in legacy:
            db.delete(achievement)
        db.commit()

    def get_current_season(self, db: Session, now: Optional[datetime] = None) -> Season:
        current = now or datetime.now(timezone.utc)
        quarter = ((current.month - 1) // 3) + 1
        start_month = (quarter - 1) * 3 + 1
        start_date = datetime(current.year, start_month, 1, tzinfo=timezone.utc)
        end_date = datetime(current.year + (1 if quarter == 4 else 0), 1 if quarter == 4 else start_month + 3, 1, tzinfo=timezone.utc)
        key = f"{current.year}-Q{quarter}"
        season = db.query(Season).filter(Season.key == key).first()
        if season:
            return season
        season = Season(key=key, start_date=start_date, end_date=end_date)
        db.add(season)
        db.commit()
        db.refresh(season)
        return season

    def apply_event(
        self,
        db: Session,
        user_id: int,
        event: str,
        amount: int = 1,
        event_key: str | None = None,
    ) -> List[Achievement]:
        self.ensure_definitions(db)
        user = db.get(User, user_id)
        if not user:
            return []
        season = self.get_current_season(db)

        if event == "coins_earned" and amount > 0:
            self._record_coin_transaction(db, user_id, season.id, amount, event_key=event_key, reason=event)

        completed: List[Achievement] = []
        completed.extend(self._update_standard_progress(db, user, season))
        completed.extend(self._update_season_progress(db, user, season))
        db.commit()
        return completed

    def apply_season_finalization(self, db: Session, season_id: int, leaderboard_user_ids: list[int]) -> List[Achievement]:
        self.ensure_definitions(db)
        completed: List[Achievement] = []
        for idx, user_id in enumerate(leaderboard_user_ids, start=1):
            user = db.get(User, user_id)
            if not user:
                continue
            completed.extend(self._complete_by_code(db, user, "season_rank_1", 1 if idx == 1 else 0, season_id))
            completed.extend(self._complete_by_code(db, user, "season_top_3", 3 if idx <= 3 else 0, season_id))
            completed.extend(self._complete_by_code(db, user, "season_top_10", 10 if idx <= 10 else 0, season_id))
        db.commit()
        return completed

    def get_user_progress(self, db: Session, user_id: int, achievement: Achievement, season_id: Optional[int] = None) -> Optional[UserAchievement]:
        if achievement.type == "ranked" and season_id is None:
            season_id = self.get_current_season(db).id
        return db.query(UserAchievement).filter(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement.id,
            UserAchievement.season_id == season_id,
        ).first()

    def format_completion_message(self, achievements: Iterable[Achievement]) -> str:
        lines = ["🏆 Новые достижения!"]
        for achievement in achievements:
            reward = [f"+{achievement.points_reward}⭐"]
            if achievement.type == "ranked" and achievement.pts_reward:
                reward.append(f"+{achievement.pts_reward}🎖️")
            lines.append(f"{achievement.icon} {achievement.name} ({' / '.join(reward)})")
        return "\n".join(lines)

    def _update_standard_progress(self, db: Session, user: User, season: Season) -> List[Achievement]:
        approved_q = db.query(Location).filter(Location.user_id == user.id, Location.status == "approved")
        approved = approved_q.all()
        approved_count = len(approved)

        completed: List[Achievement] = []
        completed.extend(self._complete_by_code(db, user, "first_approved_location", approved_count, None))
        completed.extend(self._complete_by_code(db, user, "approved_25_locations", approved_count, None))
        completed.extend(self._complete_by_code(db, user, "approved_50_locations", approved_count, None))
        completed.extend(self._complete_by_code(db, user, "approved_100_locations", approved_count, None))
        completed.extend(self._complete_by_code(db, user, "earn_1000_coins", int(user.points or 0), None))
        completed.extend(self._complete_by_code(db, user, "earn_5000_coins", int(user.points or 0), None))

        unique_tags = (
            db.query(func.count(func.distinct(LocationTag.tag_id)))
            .join(Location, Location.id == LocationTag.location_id)
            .filter(Location.user_id == user.id, Location.status == "approved")
            .scalar()
            or 0
        )
        completed.extend(self._complete_by_code(db, user, "use_20_unique_tags", int(unique_tags), None))

        day_values = [self._dt(loc.moderated_at).date() for loc in approved if loc.moderated_at]
        completed.extend(self._complete_by_code(db, user, "active_10_days", len(set(day_values)), None))

        completed.extend(self._complete_by_code(db, user, "clean_streak_5", self._compute_streak(db, user.id), None))
        completed.extend(self._complete_by_code(db, user, "approve_5_in_24h", self._max_window(approved, 24, season=None), None))
        return completed

    def _update_season_progress(self, db: Session, user: User, season: Season) -> List[Achievement]:
        approved = self._approved_in_season(db, user.id, season)
        completed: List[Achievement] = []
        completed.extend(self._complete_by_code(db, user, "season_add_5_locations", len(approved), season.id))
        completed.extend(self._complete_by_code(db, user, "season_add_3_in_24h", self._max_window(approved, 24, season=season), season.id))
        completed.extend(self._complete_by_code(db, user, "season_add_5_in_2_days", self._max_window(approved, 48, season=season), season.id))
        completed.extend(self._complete_by_code(db, user, "season_clean_streak_5", self._compute_streak(db, user.id, season), season.id))

        first_approved = approved[0] if approved else None
        in_first_3_days = 1 if first_approved and self._dt(first_approved.moderated_at) <= self._dt(season.start_date) + timedelta(days=3) else 0
        completed.extend(self._complete_by_code(db, user, "season_first_3_days", in_first_3_days, season.id))

        coins_earned = (
            db.query(func.coalesce(func.sum(CoinTransaction.amount), 0))
            .filter(CoinTransaction.user_id == user.id, CoinTransaction.season_id == season.id, CoinTransaction.amount > 0)
            .scalar()
            or 0
        )
        completed.extend(self._complete_by_code(db, user, "season_earn_1000_coins", int(coins_earned), season.id))
        return completed

    def _complete_by_code(self, db: Session, user: User, code: str, progress_value: int, season_id: int | None) -> List[Achievement]:
        achievement = db.query(Achievement).filter(Achievement.code == code).first()
        if not achievement:
            return []
        progress_entry = self._get_or_create_progress(db, user.id, achievement.id, season_id if achievement.type == "ranked" else None)
        if progress_entry.is_completed:
            return []

        target = self._target_for(achievement)
        progress_entry.progress = max(0, int(progress_value))
        if progress_entry.progress >= target:
            progress_entry.progress = target
            progress_entry.is_completed = True
            progress_entry.earned_at = datetime.now(timezone.utc)
            self._apply_reward(user, achievement)
            user.achievements_count = int(user.achievements_count or 0) + 1
            return [achievement]
        return []

    def _record_coin_transaction(self, db: Session, user_id: int, season_id: int, amount: int, event_key: str | None, reason: str) -> None:
        if event_key:
            exists = db.query(CoinTransaction.id).filter(CoinTransaction.event_key == event_key).first()
            if exists:
                return
        tx = CoinTransaction(user_id=user_id, season_id=season_id, amount=amount, event_key=event_key, reason=reason)
        db.add(tx)
        db.flush()

    def _approved_in_season(self, db: Session, user_id: int, season: Season) -> list[Location]:
        return (
            db.query(Location)
            .filter(
                Location.user_id == user_id,
                Location.status == "approved",
                Location.moderated_at.isnot(None),
                and_(Location.moderated_at >= season.start_date, Location.moderated_at < season.end_date),
            )
            .order_by(Location.moderated_at.asc(), Location.id.asc())
            .all()
        )

    def _compute_streak(self, db: Session, user_id: int, season: Season | None = None) -> int:
        q = db.query(Location).filter(Location.user_id == user_id, Location.status.in_(["approved", "rejected"]), Location.moderated_at.isnot(None))
        if season:
            q = q.filter(and_(Location.moderated_at >= season.start_date, Location.moderated_at < season.end_date))
        events = q.order_by(Location.moderated_at.asc(), Location.id.asc()).all()
        streak = 0
        best = 0
        for loc in events:
            if loc.status == "approved":
                streak += 1
                best = max(best, streak)
            else:
                streak = 0
        return min(best, 5)

    def _max_window(self, approved_locations: list[Location], hours: int, season: Season | None) -> int:
        timestamps = [self._dt(loc.moderated_at) for loc in approved_locations if loc.moderated_at]
        timestamps.sort()
        best = 0
        left = 0
        for right, cur in enumerate(timestamps):
            while left <= right and cur - timestamps[left] > timedelta(hours=hours):
                left += 1
            best = max(best, right - left + 1)
        return best

    def _target_for(self, achievement: Achievement) -> int:
        try:
            return int((json.loads(achievement.conditions) or {}).get("target", 1))
        except Exception:
            return 1

    def _get_or_create_progress(self, db: Session, user_id: int, achievement_id: int, season_id: Optional[int]) -> UserAchievement:
        entry = db.query(UserAchievement).filter(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement_id,
            UserAchievement.season_id == season_id,
        ).first()
        if entry:
            return entry
        entry = UserAchievement(
            user_id=user_id,
            achievement_id=achievement_id,
            season_id=season_id,
            progress=0,
            is_completed=False,
        )
        db.add(entry)
        db.flush()
        return entry

    def _apply_reward(self, user: User, achievement: Achievement) -> None:
        user.points = int(user.points or 0) + int(achievement.points_reward or 0)
        user.total_gp = max(int(user.total_gp or 0) + int(achievement.pts_reward or 0), 0)

    @staticmethod
    def _dt(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
