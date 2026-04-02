from bot.services.achievements_manager import DEFINITIONS


def test_achievements_have_standard_and_ranked_types():
    types = {item.type for item in DEFINITIONS}
    assert "standard" in types
    assert "ranked" in types


def test_achievement_texts_are_russian_without_approved_word():
    for item in DEFINITIONS:
        assert "approved" not in item.name.lower()
        assert "approved" not in item.description.lower()
