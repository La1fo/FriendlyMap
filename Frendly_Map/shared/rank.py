from __future__ import annotations

RANK_GP_STEP = 100


def get_rank_progress(total_gp: int) -> dict[str, int | str]:
    total_gp = max(int(total_gp), 0)
    rank_level = (total_gp // RANK_GP_STEP) + 1
    gp_in_rank = total_gp % RANK_GP_STEP
    gp_to_next_rank = RANK_GP_STEP if gp_in_rank == 0 else (RANK_GP_STEP - gp_in_rank)
    return {
        "total_gp": total_gp,
        "rank_level": rank_level,
        "gp_in_rank": gp_in_rank,
        "gp_to_next_rank": gp_to_next_rank,
        "rank_name": f"Ранг {rank_level}",
    }
