import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from bot.models.achievement import Achievement
from bot.models.season import Season
from bot.models.user import User
from bot.models.user_achievement import UserAchievement


@dataclass(frozen=True)
class AchievementDefinition:
    code: str
    name: str
    description: str
    icon: str
    type: str  # standard | ranked
    event: str
    target: int
    points_reward: int
    pts_reward: int = 0

    def conditions_json(self) -> str:
        return json.dumps({"event": self.event, "target": self.target}, ensure_ascii=False)


DEFINITIONS: List[AchievementDefinition] = [
    AchievementDefinition(
        code="first_location",
        name="Первый маркер",
        description="Добавь первую локацию",
        icon="🗺️",
        type="standard",
        event="location_submitted",
        target=1,
        points_reward=10,
    ),
    AchievementDefinition(
        code="first_approved",
        name="Проверено модератором",
        description="Первая одобренная локация",
        icon="✅",
        type="standard",
        event="location_approved",
        target=1,
        points_reward=20,
    ),
    AchievementDefinition(
        code="season_explorer",
        name="Сезонный исследователь",
        description="Добавь 5 локаций за сезон",
        icon="🏕️",
        type="ranked",
        event="location_submitted",
        target=5,
        points_reward=20,
        pts_reward=5,
    ),
    AchievementDefinition(
        code="season_pathfinder",
        name="Сезонный первопроходец",
        description="3 одобренные локации за сезон",
        icon="🥇",
        type="ranked",
        event="location_approved",
        target=3,
        points_reward=30,
        pts_reward=10,
    ),
]


class AchievementsManager:
    def ensure_definitions(self, db: Session) -> None:
        for definition in DEFINITIONS:
            achievement = db.query(Achievement).filter(Achievement.code == definition.code).first()
            if not achievement:
                achievement = Achievement(
                    code=definition.code,
                    name=definition.name,
                    description=definition.description,
                    icon=definition.icon,
                    points_reward=definition.points_reward,
                    pts_reward=definition.pts_reward,
                    type=definition.type,
                    is_seasonal=definition.type == "ranked",
                    conditions=definition.conditions_json(),
                )
                db.add(achievement)
            else:
                achievement.name = definition.name
                achievement.description = definition.description
                achievement.icon = definition.icon
                achievement.points_reward = definition.points_reward
                achievement.pts_reward = definition.pts_reward
                achievement.type = definition.type
                achievement.is_seasonal = definition.type == "ranked"
                achievement.conditions = definition.conditions_json()
        db.commit()

    def get_current_season(self, db: Session, now: Optional[datetime] = None) -> Season:
        current = now or datetime.now(timezone.utc)
        quarter = ((current.month - 1) // 3) + 1
        start_month = (quarter - 1) * 3 + 1
        start_date = datetime(current.year, start_month, 1, tzinfo=timezone.utc)
        if quarter == 4:
            end_date = datetime(current.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(current.year, start_month + 3, 1, tzinfo=timezone.utc)
        key = f"{current.year}-Q{quarter}"

        season = db.query(Season).filter(Season.key == key).first()
        if season:
            return season

        season = Season(key=key, start_date=start_date, end_date=end_date)
        db.add(season)
        db.commit()
        db.refresh(season)
        return season

    def apply_event(self, db: Session, user_id: int, event: str, amount: int = 1) -> List[Achievement]:
        self.ensure_definitions(db)
        user = db.get(User, user_id)
        if not user:
            return []

        season = self.get_current_season(db)
        definitions = [definition for definition in DEFINITIONS if definition.event == event]
        if not definitions:
            return []

        completed: List[Achievement] = []

        for definition in definitions:
            achievement = db.query(Achievement).filter(Achievement.code == definition.code).first()
            if not achievement:
                continue

            season_id = season.id if achievement.type == "ranked" else None
            progress_entry = self._get_or_create_progress(db, user_id, achievement.id, season_id)

            if progress_entry.is_completed:
                continue

            progress_entry.progress += amount
            target = definition.target

            if progress_entry.progress >= target:
                progress_entry.progress = target
                progress_entry.is_completed = True
                progress_entry.earned_at = datetime.now(timezone.utc)
                self._apply_reward(user, achievement)
                user.achievements_count += 1
                completed.append(achievement)

        db.commit()
        return completed

    def get_user_progress(
        self,
        db: Session,
        user_id: int,
        achievement: Achievement,
        season_id: Optional[int] = None,
    ) -> Optional[UserAchievement]:
        if achievement.type == "ranked" and season_id is None:
            season_id = self.get_current_season(db).id
        return (
            db.query(UserAchievement)
            .filter(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_id == achievement.id,
                UserAchievement.season_id == season_id,
            )
            .first()
        )

    def _get_or_create_progress(
        self, db: Session, user_id: int, achievement_id: int, season_id: Optional[int]
    ) -> UserAchievement:
        entry = (
            db.query(UserAchievement)
            .filter(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_id == achievement_id,
                UserAchievement.season_id == season_id,
            )
            .first()
        )
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
        user.points += achievement.points_reward
        if achievement.type == "ranked":
            user.total_gp = max(int(user.total_gp or 0) + int(achievement.pts_reward or 0), 0)

    def format_completion_message(self, achievements: Iterable[Achievement]) -> str:
        lines = [
            "🏆 Новые достижения!",
        ]
        for achievement in achievements:
            reward = [f"+{achievement.points_reward}⭐"]
            if achievement.type == "ranked" and achievement.pts_reward:
                reward.append(f"+{achievement.pts_reward}🎖️")
            lines.append(f"{achievement.icon} {achievement.name} ({' / '.join(reward)})")
        return "\n".join(lines)
