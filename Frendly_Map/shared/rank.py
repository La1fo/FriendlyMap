from __future__ import annotations

from typing import Any

RANK_GP_STEP = 100
CARTOGRAPHER_BASE_GP = 900
MASTER_CARTOGRAPHER_GP = 1300
MASTER_CARTOGRAPHER_EXTRA_GP = MASTER_CARTOGRAPHER_GP - CARTOGRAPHER_BASE_GP
MASTER_CARTOGRAPHER_TOP_LIMIT = 10

_BASE_RANKS: list[tuple[int, str]] = [
    (1, "🟢 Исследователь 1"),
    (2, "🟢 Исследователь 2"),
    (3, "🟢 Исследователь 3"),
    (4, "🔵 Путешественник 1"),
    (5, "🔵 Путешественник 2"),
    (6, "🔵 Путешественник 3"),
    (7, "🟡 Первооткрыватель 1"),
    (8, "🟡 Первооткрыватель 2"),
    (9, "🟡 Первооткрыватель 3"),
]

CARTOGRAPHER_LEVEL = 10
MASTER_CARTOGRAPHER_LEVEL = 11
CARTOGRAPHER_NAME = "🟣 Картограф"
MASTER_CARTOGRAPHER_NAME = "⭐ Мастер-картограф"


def is_top10_player(
    leaderboard_position: int | None = None,
    is_top10: bool | None = None,
) -> bool:
    if is_top10 is not None:
        return bool(is_top10)
    return leaderboard_position is not None and int(leaderboard_position) <= MASTER_CARTOGRAPHER_TOP_LIMIT


def get_rank_progress(
    total_gp: int,
    leaderboard_position: int | None = None,
    is_top10: bool | None = None,
) -> dict[str, int | str]:
    total_gp = max(int(total_gp), 0)
    top10 = is_top10_player(leaderboard_position=leaderboard_position, is_top10=is_top10)

    if total_gp >= MASTER_CARTOGRAPHER_GP and top10:
        return {
            "total_gp": total_gp,
            "rank_level": MASTER_CARTOGRAPHER_LEVEL,
            "gp_in_rank": MASTER_CARTOGRAPHER_EXTRA_GP,
            "gp_to_next_rank": 0,
            "rank_name": MASTER_CARTOGRAPHER_NAME,
        }

    if total_gp >= CARTOGRAPHER_BASE_GP:
        gp_in_rank = min(total_gp - CARTOGRAPHER_BASE_GP, MASTER_CARTOGRAPHER_EXTRA_GP)
        gp_to_next_rank = max(MASTER_CARTOGRAPHER_EXTRA_GP - gp_in_rank, 0)
        return {
            "total_gp": total_gp,
            "rank_level": CARTOGRAPHER_LEVEL,
            "gp_in_rank": gp_in_rank,
            "gp_to_next_rank": gp_to_next_rank,
            "rank_name": CARTOGRAPHER_NAME,
        }

    rank_level = (total_gp // RANK_GP_STEP) + 1
    gp_in_rank = total_gp % RANK_GP_STEP
    gp_to_next_rank = RANK_GP_STEP if gp_in_rank == 0 else (RANK_GP_STEP - gp_in_rank)
    rank_name = dict(_BASE_RANKS)[rank_level]
    return {
        "total_gp": total_gp,
        "rank_level": rank_level,
        "gp_in_rank": gp_in_rank,
        "gp_to_next_rank": gp_to_next_rank,
        "rank_name": rank_name,
    }


def format_rank_gp(rank_progress: dict[str, Any]) -> str:
    rank_name = str(rank_progress["rank_name"])
    gp_in_rank = int(rank_progress["gp_in_rank"])
    if rank_name == MASTER_CARTOGRAPHER_NAME:
        return "GP: 400/400"
    if rank_name == CARTOGRAPHER_NAME:
        return f"GP: {gp_in_rank}/400"
    return f"GP: {gp_in_rank}/100"
