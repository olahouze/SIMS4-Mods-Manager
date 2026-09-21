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
    r"^(?:(?:the|les|die|los|i|gli|de|os)\s*)?sims(?:™|®)?\s*4(?:\s*[:\-–—]?\s*(?:base\s*game|jeu\s*de\s*base|basisspiel|juego\s*base|gioco\s*base|\(?\s*(?:for|pour)?\s*(?:pc\s*(?:or|/|and|et|oder)\s*mac|pc|mac|windows|osx|linux)\s*\)?))?$|"
    r"^ts4(?:\s*[:\-–—]?\s*(?:base\s*game|jeu\s*de\s*base|basisspiel|\(?\s*(?:for|pour)?\s*(?:pc\s*(?:or|/|and|et|oder)\s*mac|pc|mac|windows|osx|linux)\s*\)?))?$|"
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
    # Stuff Packs (SP)
    "luxury party": ("SP01", "Luxury Party / Soirée de Luxe"),
    "soiree de luxe": ("SP01", "Luxury Party / Soirée de Luxe"),
    "perfect patio": ("SP02", "Perfect Patio / Ambiance Patio"),
    "ambiance patio": ("SP02", "Perfect Patio / Ambiance Patio"),
    "cool kitchen": ("SP03", "Cool Kitchen / En Cuisine"),
    "en cuisine": ("SP03", "Cool Kitchen / En Cuisine"),
    "spooky": ("SP04", "Spooky / Accessoires Effrayants"),
    "accessoires effrayants": ("SP04", "Spooky / Accessoires Effrayants"),
    "movie hangout": ("SP05", "Movie Hangout / Comme au Cinéma"),
    "comme au cinema": ("SP05", "Movie Hangout / Comme au Cinéma"),
    "romantic garden": ("SP06", "Romantic Garden / Jardin Romantique"),
    "jardin romantique": ("SP06", "Romantic Garden / Jardin Romantique"),
    "kids room": ("SP07", "Kids Room / Chambre d'enfants"),
    "chambre d enfants": ("SP07", "Kids Room / Chambre d'enfants"),
    "backyard": ("SP08", "Backyard / En Plein Air"),
    "en plein air": ("SP08", "Backyard / En Plein Air"),
    "vintage glamour": ("SP09", "Vintage Glamour / Accessoires Vintage"),
    "accessoires vintage": ("SP09", "Vintage Glamour / Accessoires Vintage"),
    "bowling night": ("SP10", "Bowling Night / Soirée Bowling"),
    "soiree bowling": ("SP10", "Bowling Night / Soirée Bowling"),
    "fitness": ("SP11", "Fitness"),
    "toddler": ("SP12", "Toddler / Bambins"),
    "bambins": ("SP12", "Toddler / Bambins"),
    "laundry day": ("SP13", "Laundry Day / Jour de Lessive"),
    "jour de lessive": ("SP13", "Laundry Day / Jour de Lessive"),
    "my first pet": ("SP14", "My First Pet / Premier Animal"),
    "premier animal": ("SP14", "My First Pet / Premier Animal"),
    "moschino": ("SP15", "Moschino"),
    "tiny living": ("SP16", "Tiny Living / Mini-Maisons"),
    "mini maisons": ("SP16", "Tiny Living / Mini-Maisons"),
    "nifty knitting": ("SP17", "Nifty Knitting / Tricot de Pro"),
    "tricot de pro": ("SP17", "Nifty Knitting / Tricot de Pro"),
    "paranormal": ("SP18", "Paranormal"),
    "home chef hustle": ("SP19", "Home Chef Hustle / Passion Cuisine"),
    "passion cuisine": ("SP19", "Home Chef Hustle / Passion Cuisine"),
    "crystal creations": ("SP20", "Crystal Creations / Créations en Cristal"),
    "creations en cristal": ("SP20", "Crystal Creations / Créations en Cristal"),
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
        clean = text.strip().strip("'\"`[](){}").rstrip(".,;:-")
        if BASE_GAME_REGEX.fullmatch(clean):
            return True
        m = SIMS4_PREFIX_REGEX.match(clean)
        if m:
            rest = clean[m.end() :].strip(" :\\-–—.,;()[]")
            if not rest or re.fullmatch(
                r"(?i)(?:base\s*game|jeu\s*de\s*base|basisspiel|juego\s*base|gioco\s*base|(?:for|pour)?\s*(?:pc\s*(?:or|/|and|et|oder)\s*mac|pc|mac|windows|osx|linux).*)",
                rest,
            ):
                return True
        return False

    @classmethod
    def canonical_fingerprint(cls, text: str) -> str:
        """Generates an alphanumeric fingerprint without spaces, hyphens, or accents."""
        if not text:
            return ""
        name = unicodedata.normalize("NFKD", text)
        name = "".join(c for c in name if not unicodedata.combining(c))
        name = name.replace("&", "and")
        return re.sub(r"[^a-zA-Z0-9]", "", name).lower()

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

        # Clean leading bullets, dashes, brackets, colons
        clean = re.sub(r"^[\s•\*\-\–\—\d\.\)\:\[\]\(\)\{\}\"\'\`]+", "", text).strip()
        # Clean leading requirement prefixes (e.g. "Requires:", "Requirements:", "Need:", "DLC:", "Pack:")
        clean = (
            re.sub(
                r"(?i)^(?:requirements?|pr[ée]requis|prerequisites?|needs?|required(?:\s*(?:mods?|packs?|dlcs?))?|requires?|dlcs?|packs?)\s*[:\-–—\s]\s*",
                "",
                clean,
            )
            .strip()
            .strip("'\"`[](){}")
        )

        if not clean or cls.is_base_game_only(clean):
            return False, None, None

        # Check if starts with a localized Sims 4 prefix
        m_prefix = SIMS4_PREFIX_REGEX.match(clean)
        is_sims_prefixed = m_prefix is not None

        clean_fp = cls.canonical_fingerprint(clean)

        # Pre-build fingerprint map
        fp_map = {cls.canonical_fingerprint(k): v for k, v in KNOWN_DLC_NAMES.items()}

        dlc_candidate = ""
        if is_sims_prefixed:
            after_prefix = clean[m_prefix.end() :].strip()
            dlc_candidate = re.sub(r"^[:\-–—\s\[\]\(\)\{\}\"\'\`]+", "", after_prefix).strip()
            dlc_candidate = re.sub(r"[\s\[\]\(\)\{\}\"\'\`]+$", "", dlc_candidate).strip()
        else:
            norm_cleaned = cls._normalize_lookup_key(clean)
            if norm_cleaned in KNOWN_DLC_NAMES or clean_fp in fp_map:
                dlc_candidate = clean
            else:
                for k_fp in fp_map:
                    if k_fp == clean_fp or (len(k_fp) >= 5 and k_fp in clean_fp):
                        dlc_candidate = clean
                        break
            if not dlc_candidate and (
                DLC_KEYWORDS_REGEX.search(clean) or re.search(r"\b(?:ep|gp|sp)[\s\-_]?\d{1,2}\b", clean, re.I)
            ):
                dlc_candidate = clean

        if not dlc_candidate:
            return False, None, None

        # If what remains is just "Base Game", "Jeu de base", platform specifier, etc., not a DLC
        if re.fullmatch(
            r"(?i)\s*(?:base\s*game|jeu\s*de\s*base|basisspiel|juego\s*base|gioco\s*base|for\s+(?:pc|mac|windows).*|\(?\s*(?:pc|mac|windows).*\)?)\s*",
            dlc_candidate,
        ):
            return False, None, None

        # Clean candidate of trailing pack descriptors
        clean_name = re.sub(
            r"(?i)\s*\b(?:expansion\s*pack|game\s*pack|stuff\s*pack|kit\s*d['’]objets|pack\s*d['’]extension|pack\s*de\s*jeu|mini-?kit|dlc|ep\d+|gp\d+|sp\d+)\b\s*",
            "",
            dlc_candidate,
        ).strip(": -–—()[]{}")

        if not clean_name:
            clean_name = dlc_candidate

        # Look up in known packs dictionary via fingerprint and keys
        normalized_key = cls._normalize_lookup_key(clean_name)
        cand_fp = cls.canonical_fingerprint(clean_name)
        pack_code = None
        standard_name = clean_name

        # Check explicit pack code regex (e.g. EP01, EP1, GP05, SP13, ep-01, ep_01)
        m_code = re.search(r"\b(EP|GP|SP)[\s\-_]?(\d{1,2})\b", clean, re.IGNORECASE)
        if m_code:
            prefix = m_code.group(1).upper()
            num = int(m_code.group(2))
            pack_code = f"{prefix}{num:02d}"
            # Find display name for this pack code
            for _k, (c, std) in KNOWN_DLC_NAMES.items():
                if c == pack_code:
                    standard_name = std
                    break

        if not pack_code:
            if normalized_key in KNOWN_DLC_NAMES:
                pack_code, standard_name = KNOWN_DLC_NAMES[normalized_key]
            elif cand_fp in fp_map:
                pack_code, standard_name = fp_map[cand_fp]
            else:
                for k_fp, (code, std) in fp_map.items():
                    if k_fp in cand_fp or (len(k_fp) >= 5 and cand_fp in k_fp):
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
