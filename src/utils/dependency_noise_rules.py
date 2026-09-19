"""
Centralized registry and classification heuristics for non-mod dependency text,
author commentary, configuration instructions, and false positives in Sims 4 mod requirements.
"""
import re
from typing import List

__all__ = [
    "KNOWN_COMMENT_KEYWORDS",
    "KNOWN_COMMENT_PREFIXES",
    "is_likely_comment_or_noise",
]

# Exact or partial keywords that strongly indicate game options, technical configuration, or disclaimers
KNOWN_COMMENT_KEYWORDS: List[str] = [
    "game options",
    "options du jeu",
    "script mods allowed",
    "script mods enabled",
    "custom content",
    "enable custom content",
    "restart the game",
    "redémarrer le jeu",
    "no third-party",
    "no third party",
    "third-party library",
    "no .package file is required",
    "script-only mod",
    "does not add tuning",
    "or xml resources",
    "xml resources",
    "not required",
    "non requis",
    "pas requis",
    "recommended setup",
    "setup for this release",
    "live mode",
    "mode vie",
    "missing the gameplay",
    "better stories",
    "bad decisions",
    "who?",
    "tested on",
    "patch actual",
    "latest patch",
    "current patch",
    "compatible version",
    "supported patch",
    "do not mix with",
    "they use separate scripts",
    "separate folders",
    "legacy edition",
]

# Patterns or prefixes indicating descriptive prose or installation guidance
KNOWN_COMMENT_PREFIXES: List[str] = [
    "ea gives you",
    "the pull is",
    "if you only install",
    "install the required",
    "watch the neighborhood",
    "enter live mode",
    "get your sim",
    "you are missing",
    "the latest versions of the following",
    "requerido para el",
    "requerido para",
    "required for",
    "tested on",
    "compatible with",
]

# Regex patterns matching full sentences or conversational dialogue
CONVERSATIONAL_SENTENCE_REGEX = re.compile(
    r"(?i)\b(ea gives you|you woohoo|you save|you load|your sim is|who\?|it was victor|"
    r"you stared|you left|he’s still waiting|also it’s tuesday|"
    r"bad decisions\. better stories|missing the gameplay ecosystem|"
    r"game options\s*(?:→|->|:)|restart the game after|"
    r"script-only mod|no \.package file|do not mix with)\b"
)


def is_likely_comment_or_noise(text: str) -> bool:
    """
    Evaluates whether a candidate requirement token or phrase is an author comment,
    game instruction, narrative prose, or false positive rather than a real Sims 4 mod or DLC name.

    Returns:
        True if the text is classified as commentary / noise, False otherwise.
    """
    if not text:
        return True

    cleaned = text.strip().strip("'\"`[](){}")
    if not cleaned or len(cleaned) < 2:
        return True

    cleaned_lower = cleaned.lower()

    # 1. Check exact or containment of known comment keywords
    for kw in KNOWN_COMMENT_KEYWORDS:
        if kw in cleaned_lower:
            return True

    # 2. Check known prefixes
    for pfx in KNOWN_COMMENT_PREFIXES:
        if cleaned_lower.startswith(pfx):
            return True

    # 3. Match conversational sentences or dialogue regex
    if CONVERSATIONAL_SENTENCE_REGEX.search(cleaned):
        return True

    # 4. Filter phrases that are clearly instructional or long narrative prose
    # (e.g. phrases longer than 60 characters with punctuation and conversational verbs)
    if len(cleaned) > 55 and any(punct in cleaned for punct in [".", ",", "!", "?", "→", ">"]):
        if any(v in cleaned_lower for v in [" you ", " your ", " is ", " are ", " does ", " will ", " after "]):
            return True

    # 5. Instructional game navigation (e.g. "Game Options -> Other -> Script Mods Allowed")
    if "→" in cleaned or "->" in cleaned:
        return True

    return False
