from src.utils.game_dlc_matcher import GameDlcMatcher


def test_base_game_detection():
    # Base game only strings should NOT be classified as DLCs
    base_examples = [
        "The Sims 4",
        "Les Sims 4",
        "Die Sims 4",
        "Los Sims 4",
        "I Sims 4",
        "Sims 4",
        "TS4",
        "The Sims 4 Base Game",
        "Les Sims 4 Jeu de base",
        "Sims 4 Basisspiel",
        "None",
        "aucun",
        "n/a",
    ]
    for text in base_examples:
        assert GameDlcMatcher.is_base_game_only(text), f"Failed for {text}"
        is_dlc, name, code = GameDlcMatcher.match_dlc(text)
        assert not is_dlc, f"Expected {text} not to be a DLC, got {name}"


def test_multilingual_dlc_detection():
    cases = [
        ("The Sims 4: City Living", "EP03"),
        ("The Sims 4 City Living", "EP03"),
        ("Les Sims 4 : Vie Citadine", "EP03"),
        ("Les Sims 4 Saisons", "EP05"),
        ("The Sims 4 Seasons", "EP05"),
        ("Die Sims 4 Jahreszeiten", "EP05"),
        ("The Sims 4 Get to Work", "EP01"),
        ("Les Sims 4 Au Travail", "EP01"),
        ("Die Sims 4 An die Arbeit", "EP01"),
        ("The Sims 4 Cats & Dogs", "EP04"),
        ("Les Sims 4 Chiens et Chats", "EP04"),
        ("TS4 Horse Ranch", "EP14"),
        ("The Sims 4 Lovestruck Expansion Pack", "EP16"),
        ("Les Sims 4 Coup de Foudre", "EP16"),
        ("The Sims 4 Vampires", "GP04"),
        ("The Sims 4: Realm of Magic", "GP08"),
        ("Les Sims 4 Monde Magique", "GP08"),
        ("The Sims 4 Werewolves", "GP12"),
        ("The Sims 4 Loups-Garous", "GP12"),
        ("The Sims 4 - For Rent", "EP15"),
        ("The Sims 4 Life & Death", "EP17"),
        ("The Sims 4 Tiny Living", "SP16"),
        ("Les Sims 4 Mini-Maisons", "SP16"),
        ("The Sims 4 Bowling Night", "SP10"),
        ("The Sims 4 Paranormal", "SP18"),
        ("The Sims 4 Crystal Creations", "SP20"),
        ("The Sims 4 xx", None),  # Generic unknown Sims 4 DLC
        ("The Sims 4 Custom Unknown Pack Name", None),  # Generic unknown Sims 4 DLC
        ("TS4 Any Pack Whatsoever", None),
        ("Les Sims 4 N'importe Quel Pack", None),
    ]

    for raw, expected_code in cases:
        is_dlc, name, code = GameDlcMatcher.match_dlc(raw)
        assert is_dlc is True, f"Failed to detect DLC for: {raw}"
        assert name is not None, f"Expected pack name for: {raw}"
        if expected_code:
            assert code == expected_code, f"Expected code {expected_code} for {raw}, got {code}"


def test_regular_mods_not_dlcs():
    mod_examples = [
        "WickedWhims",
        "Basemental Drugs",
        "MC Command Center",
        "Nisa's Wicked Perversions",
        "Kritical's Dreams of Surrender",
        "Lumpinou Open Love",
        "XML Injector",
    ]
    for mod in mod_examples:
        is_dlc, _, _ = GameDlcMatcher.match_dlc(mod)
        assert not is_dlc, f"Mod {mod} should not be classified as DLC"


def test_dlc_formatting_variations():
    """DLC detection with hyphens, underscores, merged words, and pack codes."""
    variations = [
        ("get-to-work", "EP01"),
        ("gettowork", "EP01"),
        ("get_to_work", "EP01"),
        ("GetToWork", "EP01"),
        ("au-travail", "EP01"),
        ("autravail", "EP01"),
        ("chiens-et-chats", "EP04"),
        ("chiensetchats", "EP04"),
        ("EP01", "EP01"),
        ("ep-01", "EP01"),
        ("EP_01", "EP01"),
        ("GP04", "GP04"),
        ("sp20", "SP20"),
    ]
    for text, expected_code in variations:
        is_dlc, name, code = GameDlcMatcher.match_dlc(text)
        assert is_dlc is True, f"Failed for {text}"
        assert code == expected_code, f"Expected {expected_code} for {text}, got {code}"
