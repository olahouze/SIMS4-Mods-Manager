import random
import re
import unicodedata
from pathlib import Path
from typing import Optional


def sanitize_filename(name: str) -> str:
    """Sanitizes file names to be valid on Windows."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = clean.strip().replace(" ", "_")
    return clean or "Mod"


def sanitize_mod_folder_name(name: str) -> str:
    """
    Sanitizes a name to contain ONLY alphanumeric characters (A-Z, a-z, 0-9) and underscores.
    Strips spaces, apostrophes (', ’, `), accents/diacritics, and special characters.
    """
    if not name:
        return "Mod"
    # 1. Unicode decomposition to strip accents (e.g. 'é' -> 'e', 'ü' -> 'u')
    normalized = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode("ASCII")
    # 2. Remove apostrophes completely
    normalized = normalized.replace("'", "").replace("’", "").replace("`", "")
    # 3. Replace any character that is NOT alphanumeric or underscore with an underscore
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", normalized)
    # 4. Collapse multiple underscores into one and trim edges
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "Mod"


def generate_unique_mod_folder_name(source: str, title: str, mods_dir: Optional[Path] = None) -> str:
    """
    Generates a folder name with strictly alphanumeric characters and underscores,
    ending with a random 3-digit number `_xxx` to eliminate collision risks.
    Format: `{clean_source}_{clean_title}_{random_3_digits}`
    """
    clean_source = sanitize_mod_folder_name(source)
    clean_title = sanitize_mod_folder_name(title)

    for _ in range(50):
        rand_suffix = f"{random.randint(100, 999)}"
        folder_name = f"{clean_source}_{clean_title}_{rand_suffix}"
        if not mods_dir or not (mods_dir / folder_name).exists():
            return folder_name

    return f"{clean_source}_{clean_title}_{random.randint(1000, 9999)}"
