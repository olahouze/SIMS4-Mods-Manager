"""
Backward compatibility re-export of dependency noise rules from src.utils.
"""

from src.utils.dependency_noise_rules import (
    KNOWN_COMMENT_KEYWORDS,
    KNOWN_COMMENT_PREFIXES,
    is_likely_comment_or_noise,
)

__all__ = [
    "KNOWN_COMMENT_KEYWORDS",
    "KNOWN_COMMENT_PREFIXES",
    "is_likely_comment_or_noise",
]
