# bot/utils/rank.py
from __future__ import annotations

RANK_SEQUENCE = [
    "ИССЛЕДОВАТЕЛЬ 1",
    "ИССЛЕДОВАТЕЛЬ 2",
    "ИССЛЕДОВАТЕЛЬ 3",
    "ПУТЕШЕСТВЕННИК 1",
    "ПУТЕШЕСТВЕННИК 2",
    "ПУТЕШЕСТВЕННИК 3",
    "ПЕРВООТКРЫВАТЕЛЬ 1",
    "ПЕРВООТКРЫВАТЕЛЬ 2",
    "ПЕРВООТКРЫВАТЕЛЬ 3",
]

POINTS_PER_RANK = 100
MASTER_CARTOGRAPHER_MIN_POINTS = 400
MASTER_CARTOGRAPHER_TOP_LIMIT = 10


def get_user_rank_display(points: int, leaderboard_position: int | None = None) -> str:
    points = max(int(points), 0)

    if points >= MASTER_CARTOGRAPHER_MIN_POINTS and leaderboard_position and leaderboard_position <= MASTER_CARTOGRAPHER_TOP_LIMIT:
        return "МАСТЕР-КАРТОГРАФ"

    tier_index = points // POINTS_PER_RANK
    if tier_index < len(RANK_SEQUENCE):
        return RANK_SEQUENCE[tier_index]

    return "МАСТЕР"


def get_rank_progress(points: int) -> tuple[int, int]:
    points = max(int(points), 0)
    return points // POINTS_PER_RANK, points % POINTS_PER_RANK


def get_rank_points(points: int) -> int:
    _, points_in_rank = get_rank_progress(points)
    return points_in_rank


def get_rank_title(points: int, leaderboard_position: int | None = None) -> str:
    return get_user_rank_display(points, leaderboard_position)
