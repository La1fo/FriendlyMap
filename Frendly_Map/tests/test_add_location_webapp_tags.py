from pathlib import Path


def test_add_location_no_longer_has_bot_tag_selection_states():
    source = Path("bot/handlers/add_location.py").read_text(encoding="utf-8")

    assert "ASK_TAG_CATEGORY" not in source
    assert "ASK_TAG_PICK" not in source
    assert "CB_TAG_TOGGLE" not in source
    assert "CB_TAG_CAT" not in source


def test_add_location_uses_webapp_tags_payload():
    source = Path("bot/handlers/add_location.py").read_text(encoding="utf-8")

    assert "tag_ids_json" in source
    assert "selected_tag_ids" in source
    assert "next_state\": ASK_PHOTO" in source
