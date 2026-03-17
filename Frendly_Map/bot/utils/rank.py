from shared.rank import get_rank_progress as shared_get_rank_progress


def get_rank_progress(total_gp: int) -> tuple[int, int]:
    payload = shared_get_rank_progress(total_gp)
    return int(payload["rank_level"]) - 1, int(payload["gp_in_rank"])


def get_rank_points(total_gp: int) -> int:
    payload = shared_get_rank_progress(total_gp)
    return int(payload["gp_in_rank"])


def get_user_rank_display(total_gp: int, leaderboard_position: int | None = None) -> str:
    payload = shared_get_rank_progress(total_gp)
    return str(payload["rank_name"])


def get_rank_title(total_gp: int, leaderboard_position: int | None = None) -> str:
    return get_user_rank_display(total_gp, leaderboard_position)
