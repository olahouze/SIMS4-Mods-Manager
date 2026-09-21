"""
Dependency string normalization and official Sims 4 DLC/base-game matching helpers.
Consolidates duplicated parsing logic across dependency resolver and UI dialogs.
"""

import re
from typing import Tuple, Optional
from src.utils.game_dlc_matcher import GameDlcMatcher, SIMS4_PREFIX_REGEX

__all__ = [
    "clean_dependency_title",
    "detect_game_dlc_or_base_game",
]

CLEAN_PREFIX_REGEX = re.compile(
    r"(?i)^(?:requirements?|pr[ée]requis|prerequisites?|needs?|required(?:\s*(?:mods?|packs?|dlcs?))?|requires?|dlcs?|packs?)\s*[:\-–—\s]\s*"
)
STRIP_LEADING_CHARS_REGEX = re.compile(r"^[\s•\*\-\–\—\d\.\)\:\[\]\(\)\{\}\"\'\`]+")


def clean_dependency_title(title: str) -> str:
    """Strips bullets, numbering, punctuation, and requirement prefixes from dependency text."""
    if not title:
        return ""
    cleaned = STRIP_LEADING_CHARS_REGEX.sub("", title).strip()
    cleaned = CLEAN_PREFIX_REGEX.sub("", cleaned).strip().strip("'\"`[](){}")
    return cleaned


def detect_game_dlc_or_base_game(clean_title: str) -> Tuple[bool, bool, Optional[str], Optional[str]]:
    """
    Analyzes a cleaned dependency title to determine if it is the base game or an official DLC.
    Returns: (is_base_game, is_dlc, dlc_name, dlc_code)
    """
    if not clean_title:
        return False, False, None, None

    if GameDlcMatcher.is_base_game_only(clean_title):
        return True, True, "Jeu de base", "BASE_GAME"

    starts_with_sims4 = bool(SIMS4_PREFIX_REGEX.match(clean_title))
    matched, matched_name, matched_code = GameDlcMatcher.match_dlc(clean_title)

    if matched or starts_with_sims4:
        clean_extracted_name = re.sub(
            r"^(?:(?:the|les|die|los|i|gli|de|os)\s*)?sims(?:™|®)?\s*4\s*[:\-–—]?\s*",
            "",
            clean_title,
            flags=re.IGNORECASE,
        ).strip()
        return False, True, matched_name or clean_extracted_name or clean_title, matched_code

    return False, False, None, None
