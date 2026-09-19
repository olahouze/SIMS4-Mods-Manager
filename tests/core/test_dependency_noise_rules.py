from src.services.dependency_noise_rules import is_likely_comment_or_noise
from src.services.dependency_resolver import resolve_mod_dependencies


def test_is_likely_comment_or_noise_game_options():
    assert is_likely_comment_or_noise("Script Mods enabled in Game Options") is True
    assert is_likely_comment_or_noise("Game Options → Other → Enable Custom Content") is True
    assert is_likely_comment_or_noise("Restart the game after enabling those options") is True


def test_is_likely_comment_or_noise_disclaimers():
    assert is_likely_comment_or_noise("No third-party library or framework is required") is True
    assert is_likely_comment_or_noise("No .package file is required. Conversation Lock is a script-only mod") is True
    assert is_likely_comment_or_noise("does not add tuning") is True
    assert is_likely_comment_or_noise("or XML resources") is True
    assert is_likely_comment_or_noise("Not required:") is True


def test_is_likely_comment_or_noise_narrative_dialogue():
    phrase = "EA gives you Flirty. You WooHoo. You save. You load. Your Sim is like"
    assert is_likely_comment_or_noise(phrase) is True
    assert is_likely_comment_or_noise("“Who?”") is True
    assert is_likely_comment_or_noise("If you only install Confidence Cascade") is True
    assert is_likely_comment_or_noise("Bad decisions. Better stories") is True


def test_is_likely_comment_or_noise_real_mods_never_filtered():
    # Real mods must NEVER be misclassified as noise
    assert is_likely_comment_or_noise("WickedWhims") is False
    assert is_likely_comment_or_noise("Nisa's Wicked Perversions") is False
    assert is_likely_comment_or_noise("Lot 51 Core Library") is False
    assert is_likely_comment_or_noise("XML Injector") is False
    assert is_likely_comment_or_noise("Lumpinou's Toolbox") is False
    assert is_likely_comment_or_noise("DD for Kritical's Devices") is False
    assert is_likely_comment_or_noise("Cats & Dogs") is False


def test_resolve_mod_dependencies_with_noise_and_overrides():
    from unittest.mock import MagicMock

    raw_deps = [
        {"source": "loverslab", "remote_id": "", "title": "Script Mods enabled in Game Options", "url": ""},
        {"source": "loverslab", "remote_id": "", "title": "Custom Overridden Note", "url": ""},
    ]

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None

    # User explicitly qualifies one as COMMENT and one as MOD
    overrides = {
        "Script Mods enabled in Game Options": "COMMENT",
        "Custom Overridden Note": "MOD",
    }

    items = resolve_mod_dependencies(
        raw_deps=raw_deps,
        session=mock_session,
        installed_by_remote={},
        installed_by_title={},
        is_syncing=False,
        requirements_overrides=overrides,
    )

    # 1st item should be COMMENT_NOISE
    assert items[0].status == "COMMENT_NOISE"
    assert items[0].is_comment is True

    # 2nd item should NOT be COMMENT_NOISE because user overrode it to MOD
    assert items[1].status != "COMMENT_NOISE"
    assert items[1].is_comment is False
