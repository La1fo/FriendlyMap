from types import SimpleNamespace

from bot.handlers.leaderboard import LEADERBOARD_SEPARATOR, build_leaderboard_caption
from bot.handlers.profile import build_profile_caption
from shared.rank import get_rank_progress


def test_profile_caption_uses_rank_and_gp_only():
    user = SimpleNamespace(
        username="tester",
        points=25,
        total_gp=950,
        approved_locations=4,
    )
    banner = {"title": "Профиль", "description": "Описание"}

    caption = build_profile_caption(user, banner)

    assert "🟣 Картограф" in caption
    assert "GP: 50" in caption
    assert "Общий GP" not in caption
    assert "GP в текущем ранге" not in caption


def test_leaderboard_caption_uses_rank_and_gp_only():
    users = [
        SimpleNamespace(id=1, username="alpha", first_name="Alpha", total_gp=1400),
        SimpleNamespace(id=2, username="beta", first_name="Beta", total_gp=950),
    ]
    current_user = users[1]
    banner = {"title": "Лидеры", "description": "Описание"}

    caption = build_leaderboard_caption(
        users=users,
        current_user=current_user,
        position=2,
        total=20,
        banner=banner,
        current_name="beta",
    )

    assert "⭐ Мастер-картограф · GP: 500" in caption
    assert "🟣 Картограф · GP: 50" in caption
    assert "Общий GP" not in caption
    assert "GP в ранге" not in caption
    assert "GP в текущем ранге" not in caption
    assert LEADERBOARD_SEPARATOR in caption
    assert len(LEADERBOARD_SEPARATOR) >= 20


def test_profile_and_leaderboard_use_same_rank_source_for_master():
    user = SimpleNamespace(
        id=1,
        username="master",
        first_name="Master",
        total_gp=1450,
        points=0,
        approved_locations=12,
    )
    banner_profile = {"title": "Профиль", "description": "Описание"}
    banner_leader = {"title": "Лидеры", "description": "Описание"}

    profile_caption = build_profile_caption(user, banner_profile, leaderboard_position=1)
    leaderboard_caption = build_leaderboard_caption(
        users=[user],
        current_user=user,
        position=1,
        total=10,
        banner=banner_leader,
        current_name="master",
    )
    rank = get_rank_progress(1450, leaderboard_position=1)

    assert rank["rank_name"] in profile_caption
    assert rank["rank_name"] in leaderboard_caption
    assert f"GP: {rank['gp_in_rank']}" in profile_caption
    assert f"GP: {rank['gp_in_rank']}" in leaderboard_caption
