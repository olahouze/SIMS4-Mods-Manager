import re
from datetime import datetime
from typing import Optional


def parse_flexible_date(date_val: Optional[str]) -> Optional[datetime]:
    """
    Parses a date string from various common formats (ISO 8601, LoversLab, European, US).
    Returns a datetime object or None if unparseable.
    """
    if not date_val or not isinstance(date_val, str):
        return None

    clean_val = date_val.strip()
    if not clean_val:
        return None

    # Try ISO format directly
    try:
        return datetime.fromisoformat(clean_val.replace("Z", "+00:00"))
    except ValueError:
        pass

    # Common strptime patterns
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(clean_val, fmt)
        except ValueError:
            continue

    return None


def normalize_version(version_str: Optional[str]) -> str:
    """
    Extracts and standardizes version numbers from messy version strings.
    Example: 'v1.4.2a (Update)' -> '1.4.2a'
    """
    if not version_str:
        return ""

    s = version_str.strip()
    # Strip common prefixes like 'version', 'ver', 'v' (longest first to avoid partial match)
    s = re.sub(r"^(?:version|ver|v)\.?\s*", "", s, flags=re.IGNORECASE)
    # Strip trailing parentheses or notes
    s = re.sub(r"\s*\(.*?\)$", "", s).strip()
    return s
