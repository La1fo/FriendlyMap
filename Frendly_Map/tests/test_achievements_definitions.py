from bot.services.achievements_manager import DEFINITIONS


def test_achievements_have_standard_and_ranked_types():
    types = {item.type for item in DEFINITIONS}
    assert "standard" in types
    assert "ranked" in types
