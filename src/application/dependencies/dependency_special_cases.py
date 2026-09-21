"""
Special dependency cases registry (e.g. WickedWhims, XML Injector) with aliases and hardcoded remote URLs.
"""

import re
from typing import List, Dict, Any, Optional

__all__ = [
    "SPECIAL_DEPENDENCY_CASES",
    "SPECIAL_DEPENDENCY_REMOTE_IDS",
    "find_special_dependency_case",
]

SPECIAL_DEPENDENCY_CASES: List[Dict[str, Any]] = [
    {
        "title": "WickedWhims",
        "remote_id": "3169",
        "url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
        "source": "loverslab",
        "aliases": [
            "WW",
            "ww",
            "WickedWhims",
            "wickedwhims",
            "Wicked-Whims",
            "wicked-whims",
            "Wicked_Whims",
            "wicked_whims",
            "Wicked Whims",
            "wicked whims",
            "WickedWhim",
            "wickedwhim",
            "Wicked-Whim",
            "wicked-whim",
            "Wicked_Whim",
            "wicked_whim",
            "Wicked Whim",
            "wicked whim",
        ],
    },
]

SPECIAL_DEPENDENCY_REMOTE_IDS = {case["remote_id"] for case in SPECIAL_DEPENDENCY_CASES if "remote_id" in case}


def find_special_dependency_case(name: str) -> Optional[Dict[str, Any]]:
    """
    Recherche si un nom de mod correspond à l'un des cas spécifiques définis
    dans la table de correspondance (insensible à la casse, tolérant aux tirets '-',
    underscores '_', espaces et versions).
    """
    if not name:
        return None

    cleaned_name = name.strip()
    stripped_name = re.sub(r"^[\(\[\{]+|[\)\]\}]+$", "", cleaned_name).strip()
    raw_lower = stripped_name.lower()
    compressed = re.sub(r"[\s\-_.]+", "", raw_lower)

    for case in SPECIAL_DEPENDENCY_CASES:
        for alias in case.get("aliases", []):
            alias_lower = alias.strip().lower()
            alias_compressed = re.sub(r"[\s\-_.]+", "", alias_lower)

            if raw_lower == alias_lower or compressed == alias_compressed:
                return case

            if len(alias_compressed) >= 5 and alias_compressed in compressed:
                return case

    return None
