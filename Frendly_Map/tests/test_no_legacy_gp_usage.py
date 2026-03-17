from pathlib import Path


def test_profile_and_leaderboard_use_total_gp_not_pts():
    profile = Path("bot/handlers/profile.py").read_text(encoding="utf-8")
    leaderboard = Path("bot/handlers/leaderboard.py").read_text(encoding="utf-8")

    assert ".pts" not in profile
    assert ".pts" not in leaderboard
    assert "total_gp" in profile
    assert "total_gp" in leaderboard
