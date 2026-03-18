from types import SimpleNamespace

from bot.handlers.leaderboard import build_leaderboard_caption
from bot.handlers.profile import build_profile_caption


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
    assert "GP: 50/400" in caption
    assert "Общий GP" not in caption
    assert "GP в текущем ранге" not in caption


def test_leaderboard_caption_uses_rank_and_gp_only():
    users = [
        SimpleNamespace(id=1, username="alpha", first_name="Alpha", total_gp=1300),
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

    assert "⭐ Мастер-картограф · GP: 400/400" in caption
    assert "🟣 Картограф · GP: 50/400" in caption
    assert "Общий GP" not in caption
    assert "GP в ранге" not in caption
    assert "GP в текущем ранге" not in caption
