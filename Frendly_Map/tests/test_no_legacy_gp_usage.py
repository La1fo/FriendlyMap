from pathlib import Path


def test_profile_and_leaderboard_use_total_gp_not_pts():
    profile = Path("bot/handlers/profile.py").read_text(encoding="utf-8")
    leaderboard = Path("bot/handlers/leaderboard.py").read_text(encoding="utf-8")

    assert ".pts" not in profile
    assert ".pts" not in leaderboard
    assert "total_gp" in profile
    assert "total_gp" in leaderboard


def test_services_do_not_write_pts_for_rank_progress():
    gp_service = Path("bot/services/gp_service.py").read_text(encoding="utf-8")
    achievements = Path("bot/services/achievements_manager.py").read_text(encoding="utf-8")

    assert "user.pts =" not in gp_service
    assert "user.pts =" not in achievements
    assert "total_gp" in gp_service
    assert "total_gp" in achievements


def test_rank_outputs_use_shared_rank_helper():
    profile = Path("bot/handlers/profile.py").read_text(encoding="utf-8")
    leaderboard = Path("bot/handlers/leaderboard.py").read_text(encoding="utf-8")
    map_api = Path("webapp/api/map.py").read_text(encoding="utf-8")

    assert "from shared.rank import get_rank_progress" in profile
    assert "from shared.rank import get_rank_progress" in leaderboard
    assert "from shared.rank import get_rank_progress" in map_api
    assert "get_rank_progress(user.total_gp)" in profile
    assert "get_rank_progress(user.total_gp)" in leaderboard
    assert "get_rank_progress(author.total_gp if author else 0)" in map_api
