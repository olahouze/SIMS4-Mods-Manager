import re
import unicodedata
from typing import Optional, Tuple
from pathlib import Path


# Recognized multilingue Sims 4 prefixes
SIMS4_PREFIX_REGEX = re.compile(
    r"^(?:(?:the|les|die|los|i|gli|de|os)\s*)?sims(?:™|®)?\s*4\b|^ts4\b|^симс\s*4\b",
    re.IGNORECASE,
)

# Base game indicators to exclude from DLC categorization
BASE_GAME_REGEX = re.compile(
    r"^(?:(?:the|les|die|los|i|gli|de|os)\s*)?sims(?:™|®)?\s*4(?:\s*(?:base\s*game|jeu\s*de\s*base|basisspiel|juego\s*base|gioco\s*base))?$|"
    r"^ts4(?:\s*(?:base\s*game|jeu\s*de\s*base|basisspiel))?$|"
    r"^(?:base\s*game|jeu\s*de\s*base|basisspiel|juego\s*base|none|aucun|aucun[e]?|n/?a|-)$",
    re.IGNORECASE,
)

# Generic pack classification keywords
DLC_KEYWORDS_REGEX = re.compile(
    r"\b(?:expansion\s*pack|game\s*pack|stuff\s*pack|kit\s*d['’]objets|pack\s*d['’]extension|pack\s*de\s*jeu|mini-?kit|dlc|ep\d+|gp\d+|sp\d+)\b",
    re.IGNORECASE,
)

# Common known DLC / Pack nicknames and codes
KNOWN_DLC_NAMES = {
    # Expansion Packs (EP)
    "get to work": ("EP01", "Get to Work / Au Travail"),
    "au travail": ("EP01", "Get to Work / Au Travail"),
    "an die arbeit": ("EP01", "Get to Work / Au Travail"),
    "get together": ("EP02", "Get Together / Vivre Ensemble"),
    "vivre ensemble": ("EP02", "Get Together / Vivre Ensemble"),
    "city living": ("EP03", "City Living / Vie Citadine"),
    "vie citadine": ("EP03", "City Living / Vie Citadine"),
    "cats & dogs": ("EP04", "Cats & Dogs / Chiens et Chats"),
    "cats and dogs": ("EP04", "Cats & Dogs / Chiens et Chats"),
    "chiens et chats": ("EP04", "Cats & Dogs / Chiens et Chats"),
    "seasons": ("EP05", "Seasons / Saisons"),
    "saisons": ("EP05", "Seasons / Saisons"),
    "jahreszeiten": ("EP05", "Seasons / Saisons"),
    "get famous": ("EP06", "Get Famous / Heure de Gloire"),
    "heure de gloire": ("EP06", "Get Famous / Heure de Gloire"),
    "island living": ("EP07", "Island Living / Îles Paradisiaques"),
    "iles paradisiaques": ("EP07", "Island Living / Îles Paradisiaques"),
    "discover university": ("EP08", "Discover University / À la Fac"),
    "a la fac": ("EP08", "Discover University / À la Fac"),
    "eco lifestyle": ("EP09", "Eco Lifestyle / Écologie"),
    "ecologie": ("EP09", "Eco Lifestyle / Écologie"),
    "snowy escape": ("EP10", "Snowy Escape / Escapade Enneigée"),
    "escapade enneigee": ("EP10", "Snowy Escape / Escapade Enneigée"),
    "cottage living": ("EP11", "Cottage Living / Vie à la Campagne"),
    "vie a la campagne": ("EP11", "Cottage Living / Vie à la Campagne"),
    "high school years": ("EP12", "High School Years / Années Lycée"),
    "annees lycee": ("EP12", "High School Years / Années Lycée"),
    "growing together": ("EP13", "Growing Together / Grandir Ensemble"),
    "grandir ensemble": ("EP13", "Growing Together / Grandir Ensemble"),
    "horse ranch": ("EP14", "Horse Ranch / Vie au Ranch"),
    "vie au ranch": ("EP14", "Horse Ranch / Vie au Ranch"),
    "for rent": ("EP15", "For Rent / À Louer"),
    "a louer": ("EP15", "For Rent / À Louer"),
    "lovestruck": ("EP16", "Lovestruck / Coup de Foudre"),
    "coup de foudre": ("EP16", "Lovestruck / Coup de Foudre"),
    "life & death": ("EP17", "Life & Death / Vie et Mort"),
    "life and death": ("EP17", "Life & Death / Vie et Mort"),
    "vie et mort": ("EP17", "Life & Death / Vie et Mort"),
    # Game Packs (GP)
    "outdoor retreat": ("GP01", "Outdoor Retreat / Destination Nature"),
    "destination nature": ("GP01", "Outdoor Retreat / Destination Nature"),
    "spa day": ("GP02", "Spa Day / Détente au Spa"),
    "detente au spa": ("GP02", "Spa Day / Détente au Spa"),
    "dine out": ("GP03", "Dine Out / Au Resto"),
    "au resto": ("GP03", "Dine Out / Au Resto"),
    "vampires": ("GP04", "Vampires"),
    "parenthood": ("GP05", "Parenthood / Être Parents"),
    "etre parents": ("GP05", "Parenthood / Être Parents"),
    "jungle adventure": ("GP06", "Jungle Adventure / Dans la Jungle"),
    "dans la jungle": ("GP06", "Jungle Adventure / Dans la Jungle"),
    "strangerville": ("GP07", "Strangerville"),
    "realm of magic": ("GP08", "Realm of Magic / Monde Magique"),
    "monde magique": ("GP08", "Realm of Magic / Monde Magique"),
    "journey to batuu": ("GP09", "Journey to Batuu"),
    "dream home decorator": ("GP10", "Dream Home Decorator / Décoration d'Intérieur"),
    "my wedding stories": ("GP11", "My Wedding Stories / Mariage"),
    "werewolves": ("GP12", "Werewolves / Loups-Garous"),
    "loups garous": ("GP12", "Werewolves / Loups-Garous"),
}


class GameDlcMatcher:
    """
    Identifies if a mod dependency represents an official The Sims 4 DLC / Game Pack
    in multiple languages, rather than a downloadable user mod.
    """

    @classmethod
    def is_base_game_only(cls, text: str) -> bool:
        """Returns True if the text only refers to the Sims 4 base game without any pack."""
        if not text:
            return False
        clean = text.strip()
        return bool(BASE_GAME_REGEX.fullmatch(clean))

    @classmethod
    def match_dlc(cls, text: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Analyzes a dependency string.
        Returns:
            (is_dlc, pack_name, pack_code)
            - is_dlc: bool
            - pack_name: clean display name of the DLC (e.g., 'City Living')
            - pack_code: EP/GP/SP code if recognized (e.g., 'EP03'), else None
        """
        if not text:
            return False, None, None

        cleaned = text.strip().strip("'\"`[](){}")
        if cls.is_base_game_only(cleaned):
            return False, None, None

        # Check if starts with a localized Sims 4 prefix
        m_prefix = SIMS4_PREFIX_REGEX.match(cleaned)
        is_sims_prefixed = m_prefix is not None

        dlc_candidate = ""
        if is_sims_prefixed:
            # Everything after the prefix
            after_prefix = cleaned[m_prefix.end() :].strip()
            # Remove leading punctuation like ":", "-", "–", or words like "Pack", "DLC"
            dlc_candidate = re.sub(r"^[:\-–—\s]+", "", after_prefix).strip()
        else:
            # Check if it has explicit pack code or keyword (e.g. "EP01 Get to Work" or "Get to Work Expansion Pack")
            if DLC_KEYWORDS_REGEX.search(cleaned):
                dlc_candidate = cleaned

        if not dlc_candidate:
            return False, None, None

        # If what remains is just "Base Game", "Jeu de base", etc., not a DLC
        if re.fullmatch(r"(?i)\s*(base\s*game|jeu\s*de\s*base|basisspiel)\s*", dlc_candidate):
            return False, None, None

        # Clean candidate of trailing pack descriptors (e.g. "Get to Work Expansion Pack" -> "Get to Work")
        clean_name = re.sub(
            r"(?i)\s*\b(?:expansion\s*pack|game\s*pack|stuff\s*pack|kit\s*d['’]objets|pack\s*d['’]extension|pack\s*de\s*jeu|mini-?kit|dlc)\b\s*",
            "",
            dlc_candidate,
        ).strip(": -–—")

        if not clean_name:
            clean_name = dlc_candidate

        # Look up in known packs dictionary
        normalized_key = cls._normalize_lookup_key(clean_name)
        pack_code = None
        standard_name = clean_name

        if normalized_key in KNOWN_DLC_NAMES:
            pack_code, standard_name = KNOWN_DLC_NAMES[normalized_key]
        else:
            # Check partial matches in KNOWN_DLC_NAMES
            for k, (code, std) in KNOWN_DLC_NAMES.items():
                if k in normalized_key or normalized_key in k:
                    pack_code = code
                    standard_name = std
                    break

        return True, standard_name, pack_code

    @classmethod
    def _normalize_lookup_key(cls, name: str) -> str:
        """Normalizes accents, punctuation, and multiple spaces for dictionary matching."""
        name = unicodedata.normalize("NFKD", name)
        name = "".join(c for c in name if not unicodedata.combining(c))
        name = name.replace("&", "and").replace("'", "").replace("’", "")
        name = re.sub(r"[^a-zA-Z0-9\s]", " ", name)
        return re.sub(r"\s+", " ", name).strip().lower()

    @classmethod
    def is_dlc_installed_in_game(cls, pack_code: Optional[str], game_dir: Optional[Path] = None) -> Optional[bool]:
        """
        Checks if the pack (e.g., 'EP01', 'GP05') folder exists in the game installation directory.
        Returns True if detected, False if directory was found but pack folder is missing,
        or None if game directory is unknown.
        """
        if not pack_code:
            return None

        try:
            from src.services.game_service import GameService

            game_exe = GameService.get_game_exe_path()
            if not game_exe or not game_exe.exists():
                return None

            potential_roots = [
                game_exe.parent,
                game_exe.parent.parent,
                game_exe.parent.parent.parent,
            ]

            code_upper = pack_code.upper()
            for root in potential_roots:
                if root.exists():
                    candidate_folder = root / code_upper
                    if candidate_folder.is_dir():
                        return True
                    if (root / "Delta" / code_upper).is_dir():
                        return True

            return False
        except Exception:
            return None
