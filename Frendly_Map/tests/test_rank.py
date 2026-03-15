from bot.utils.rank import get_rank_points, get_user_rank_display


def test_rank_points_reset_every_100_gp():
    assert get_rank_points(0) == 0
    assert get_rank_points(99) == 99
    assert get_rank_points(100) == 0
    assert get_rank_points(101) == 1
    assert get_rank_points(260) == 60


def test_rank_grows_when_total_gp_grows():
    assert get_user_rank_display(99) == "ИССЛЕДОВАТЕЛЬ 1"
    assert get_user_rank_display(100) == "ИССЛЕДОВАТЕЛЬ 2"
