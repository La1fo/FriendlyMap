from shared.rank import format_rank_gp, get_rank_progress


def test_rank_progress_thresholds():
    cases = [
        (0, None, 1, "🟢 Исследователь 1", 0),
        (100, None, 2, "🟢 Исследователь 2", 0),
        (200, None, 3, "🟢 Исследователь 3", 0),
        (300, None, 4, "🔵 Путешественник 1", 0),
        (400, None, 5, "🔵 Путешественник 2", 0),
        (500, None, 6, "🔵 Путешественник 3", 0),
        (600, None, 7, "🟡 Первооткрыватель 1", 0),
        (700, None, 8, "🟡 Первооткрыватель 2", 0),
        (800, None, 9, "🟡 Первооткрыватель 3", 0),
        (900, None, 10, "🟣 Картограф", 0),
        (1299, 11, 10, "🟣 Картограф", 399),
        (1300, 11, 10, "🟣 Картограф", 400),
        (1300, 10, 11, "⭐ Мастер-картограф", 400),
    ]

    for total_gp, leaderboard_position, expected_level, expected_name, expected_gp in cases:
        payload = get_rank_progress(total_gp, leaderboard_position=leaderboard_position)
        assert payload["rank_level"] == expected_level
        assert payload["rank_name"] == expected_name
        assert payload["gp_in_rank"] == expected_gp


def test_rank_progress_boundaries():
    assert get_rank_progress(99)["rank_name"] == "🟢 Исследователь 1"
    assert get_rank_progress(99)["gp_in_rank"] == 99
    assert get_rank_progress(102)["rank_name"] == "🟢 Исследователь 2"
    assert get_rank_progress(102)["gp_in_rank"] == 2
    assert get_rank_progress(1300, is_top10=False)["rank_name"] == "🟣 Картограф"
    assert get_rank_progress(1300, is_top10=True)["rank_name"] == "⭐ Мастер-картограф"


def test_format_rank_gp():
    assert format_rank_gp(get_rank_progress(55)) == "GP: 55/100"
    assert format_rank_gp(get_rank_progress(950)) == "GP: 50/400"
    assert format_rank_gp(get_rank_progress(1300, leaderboard_position=1)) == "GP: 400/400"
