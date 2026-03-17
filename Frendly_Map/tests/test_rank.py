from shared.rank import get_rank_progress


def test_rank_progress_boundaries():
    assert get_rank_progress(0) == {
        "total_gp": 0,
        "rank_level": 1,
        "gp_in_rank": 0,
        "gp_to_next_rank": 100,
        "rank_name": "Ранг 1",
    }
    assert get_rank_progress(99)["rank_level"] == 1
    assert get_rank_progress(99)["gp_in_rank"] == 99
    assert get_rank_progress(100)["rank_level"] == 2
    assert get_rank_progress(100)["gp_in_rank"] == 0
    assert get_rank_progress(102)["rank_level"] == 2
    assert get_rank_progress(102)["gp_in_rank"] == 2
