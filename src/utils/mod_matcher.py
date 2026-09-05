import re
import difflib
import unicodedata
from typing import Optional, List, Tuple, Any
from src.utils.logger import logger


class ModMatcher:
    """
    Utility for normalizing mod titles, stripping prefixes (creators, tags) and suffixes
    (versions, dates, updates), and scoring similarity between parent mod dependency requirements
    and catalog / installed mods.
    """

    # Common tags and prefixes in brackets/parentheses to strip
    BRACKETED_TAGS_PATTERN = re.compile(
        r"\[(?:ts4|the\s*sims\s*4|sims\s*4|mod|wip|beta|public|release|updated?|patreon|nsfw|v\d+[^\]]*|\d{4}[^\]]*)\]",
        re.IGNORECASE,
    )

    # General bracket/parentheses matcher (for authors, versions, or tags)
    ANY_BRACKETS_PATTERN = re.compile(r"\[[^\]]*\]|\([^\)]*\)|\{[^\}]*\}")

    # Version patterns (e.g. v1.2.3, ver 4, version 2.0, 7.18.150, build 123)
    VERSION_PATTERN = re.compile(
        r"(?i)\b(?:v(?:er(?:sion)?)?\.?\s*\d+(?:\.\d+)*[a-z]?|\b\d+\.\d+(?:\.\d+)*[a-z]?\b|\bbuild\s*\d+\b|\brelease\s*\d+\b)",
    )

    # Date patterns (e.g. July 2024, 2024-05, 05/2024, 10 July 2024)
    DATE_PATTERN = re.compile(
        r"(?i)\b(?:\d{1,2}\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\s+\d{4}\b|\b\d{4}[-/]\d{2}(?:[-/]\d{2})?\b",
    )

    # Creator patterns (e.g. "by AuthorName", "par Author", "Author's ...", "Author - ...")
    CREATOR_SUFFIX_PATTERN = re.compile(
        r"(?i)\b(?:by|par|de)\s+[a-zA-Z0-9_\-]+(?:\s*['’]s)?$",
    )
    CREATOR_PREFIX_PATTERN = re.compile(
        r"(?i)^[a-zA-Z0-9_\-]+['’]s\s+",
    )
    CREATOR_DASH_PREFIX_PATTERN = re.compile(
        r"^[a-zA-Z0-9_\-]{2,20}\s*[-–:]\s+",
    )

    # Noise words to discard
    NOISE_WORDS_PATTERN = re.compile(
        r"(?i)\b(?:the\s+sims\s+4|sims\s+4|the\s+sims|sims|ts4|cc|custom\s+content|package|addon|add-on)\b",
    )

    @classmethod
    def strip_accents(cls, text: str) -> str:
        """Removes diacritical marks/accents from text."""
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    @classmethod
    def extract_author_and_version(cls, title: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Attempts to extract creator name and version from bracketed or prefixed patterns.
        Example: '[Scumbumbo] XML Injector v4' -> ('Scumbumbo', 'v4')
        """
        if not title:
            return None, None

        author = None
        version = None

        # Check for bracketed author [Author] at start
        m_author = re.match(r"^\s*\[([a-zA-Z0-9_\-\s]{2,30})\]", title)
        if m_author:
            candidate = m_author.group(1).strip()
            if not re.match(r"(?i)^(?:ts4|sims\s*4|mod|wip|public|v\d+)", candidate):
                author = candidate
        else:
            # Check for 'by Author'
            m_by = cls.CREATOR_SUFFIX_PATTERN.search(title)
            if m_by:
                by_text = m_by.group(0).strip()
                parts = by_text.split()
                if len(parts) >= 2:
                    author = parts[-1]

        # Check for version
        m_ver = cls.VERSION_PATTERN.search(title)
        if m_ver:
            version = m_ver.group(0).strip()

        return author, version

    @classmethod
    def clean_mod_title(cls, title: str) -> str:
        """
        Extracts the essential core name of a mod by stripping creator tags,
        version identifiers, dates, and noise words.
        Example: '[Scumbumbo] XML Injector v4.2 [Updated]' -> 'xml injector'
        """
        if not title:
            return ""

        # Remove bracketed tags like [TS4], [v1.2], [Scumbumbo], (Updated)
        cleaned = cls.ANY_BRACKETS_PATTERN.sub(" ", title)

        # Remove dates
        cleaned = cls.DATE_PATTERN.sub(" ", cleaned)

        # Remove version numbers
        cleaned = cls.VERSION_PATTERN.sub(" ", cleaned)

        # Remove creator suffix: '... by Author'
        cleaned = cls.CREATOR_SUFFIX_PATTERN.sub(" ", cleaned)

        # Remove creator prefix: "Scumbumbo's ..."
        cleaned = cls.CREATOR_PREFIX_PATTERN.sub(" ", cleaned)

        # Remove creator prefix with dash: "Kuttoe - Mini Mods"
        cleaned = cls.CREATOR_DASH_PREFIX_PATTERN.sub(" ", cleaned)

        # Remove noise words (sims 4, mod, etc.)
        cleaned = cls.NOISE_WORDS_PATTERN.sub(" ", cleaned)

        # Strip accents & special punctuation
        cleaned = cls.strip_accents(cleaned)
        cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", cleaned)

        # Collapse whitespace and lowercase
        cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()

        # Strip trailing singular 'mod' if preceded by something else (e.g. 'xxx mod' -> 'xxx')
        if len(cleaned.split()) > 1:
            cleaned = re.sub(r"\s+\bmod\b$", "", cleaned).strip()

        # If stripping everything resulted in empty string (e.g. mod was literally named '[TS4] Mod'),
        # fall back to basic alphanumeric lower of original
        if not cleaned:
            fallback = re.sub(r"[^a-zA-Z0-9\s]", " ", cls.strip_accents(title))
            cleaned = re.sub(r"\s+", " ", fallback).strip().lower()

        return cleaned

    @classmethod
    def get_significant_tokens(cls, cleaned_text: str) -> List[str]:
        """Returns sorted non-trivial words (length >= 2) from cleaned text."""
        tokens = [w for w in cleaned_text.split() if len(w) >= 2]
        return tokens

    @classmethod
    def match_score(
        cls,
        query: str,
        candidate_title: str,
        candidate_author: Optional[str] = None,
    ) -> float:
        """
        Calculates a match confidence score between 0.0 and 1.0 (100%).
        Higher score means higher probability that candidate_title is the mod requested in query.
        """
        if not query or not candidate_title:
            return 0.0

        q_clean = cls.clean_mod_title(query)
        c_clean = cls.clean_mod_title(candidate_title)

        if not q_clean or not c_clean:
            return 0.0

        # 1. Exact match on cleaned core names
        if q_clean == c_clean:
            return 1.0

        q_tokens = cls.get_significant_tokens(q_clean)
        c_tokens = cls.get_significant_tokens(c_clean)

        if not q_tokens or not c_tokens:
            return 0.0

        q_set = set(q_tokens)
        c_set = set(c_tokens)

        # Check token sets equality
        if q_set == c_set:
            return 0.98

        diff_c = c_set - q_set
        diff_q = q_set - c_set
        if diff_c <= {"mod", "mods"} and not diff_q:
            return 0.98
        if diff_q <= {"mod", "mods"} and not diff_c:
            return 0.98

        # If query has substantial words NOT in candidate (candidate is missing critical words)
        missing_from_candidate = [w for w in diff_q if w not in ("mod", "mods")]
        if missing_from_candidate:
            overlap = len(q_set.intersection(c_set)) / len(q_set)
            return round(0.40 * overlap, 3)

        # 2. Token containment (all query tokens are present in candidate, e.g. 'xml injector' in 'scumbumbo xml injector')
        if q_set.issubset(c_set):
            ratio = len(q_set) / max(len(c_set), 1)
            extra = diff_c - {"mod", "mods"}
            extracted_author, _ = cls.extract_author_and_version(candidate_title)
            if not extra or (candidate_author and extra <= {candidate_author.lower()}) or (extracted_author and extra <= {extracted_author.lower()}):
                return 0.95
            return round(0.80 + 0.15 * ratio, 3)

        # 3. Intersection / Jaccard token score
        intersection = q_set.intersection(c_set)
        if intersection:
            jaccard = len(intersection) / len(q_set.union(c_set))
            overlap_q = len(intersection) / len(q_set)
            if overlap_q >= 0.80:
                base_score = 0.70 + 0.20 * jaccard
            else:
                base_score = 0.40 * overlap_q + 0.20 * jaccard
        else:
            base_score = 0.0

        # Fuzzy similarity only if token overlap is already significant
        if intersection and len(intersection) >= len(q_tokens) * 0.75:
            str_ratio = difflib.SequenceMatcher(None, q_clean, c_clean).ratio()
            final_score = max(base_score, str_ratio * 0.85)
        else:
            final_score = base_score

        # Author bonus
        extracted_author, _ = cls.extract_author_and_version(query)
        if candidate_author and (extracted_author or candidate_author.lower() in query.lower()):
            if candidate_author.lower() in query.lower() or (
                extracted_author and extracted_author.lower() in candidate_author.lower()
            ):
                final_score = min(1.0, final_score + 0.10)

        return round(final_score, 3)

    @classmethod
    def find_best_catalog_match(
        cls,
        query: str,
        session,
        min_threshold: float = 0.70,
    ) -> Optional[Tuple[Any, float]]:
        """
        Searches the CatalogMod database table for the best matching mod according to regex cleaning
        and similarity score.
        Returns (catalog_mod, score) or None if no candidate exceeds min_threshold.
        """
        from src.core.database import CatalogMod

        if not query:
            return None

        # Direct remote_id check if query is digits
        if str(query).isdigit():
            direct_id = session.query(CatalogMod).filter_by(remote_id=str(query)).first()
            if direct_id:
                return direct_id, 1.0

        q_clean = cls.clean_mod_title(query)
        tokens = cls.get_significant_tokens(q_clean)

        candidate_query = session.query(CatalogMod)
        if tokens:
            from sqlalchemy import or_
            token_filters = [CatalogMod.title.ilike(f"%{tok}%") for tok in tokens[:3]]
            candidates = candidate_query.filter(or_(*token_filters)).limit(100).all()
        else:
            candidates = candidate_query.limit(50).all()

        best_mod = None
        best_score = 0.0

        for cand in candidates:
            score = cls.match_score(query, cand.title, cand.author)
            if score > best_score:
                best_score = score
                best_mod = cand

        if best_mod and best_score >= min_threshold:
            logger.debug(
                f"[ModMatcher] Match catalog trouvé pour '{query}': '{best_mod.title}' "
                f"(score={best_score:.2f} >= {min_threshold})"
            )
            return best_mod, best_score

        return None

    @classmethod
    def find_best_installed_match(
        cls,
        query: str,
        installed_mods: List[Any],
        min_threshold: float = 0.70,
    ) -> Optional[Tuple[Any, float]]:
        """
        Searches a list of InstalledMod objects for the best match for query.
        Returns (installed_mod, score) or None.
        """
        if not query or not installed_mods:
            return None

        best_mod = None
        best_score = 0.0

        for im in installed_mods:
            im_title = getattr(im, "title", "") or ""
            score = cls.match_score(query, im_title)
            if score > best_score:
                best_score = score
                best_mod = im

        if best_mod and best_score >= min_threshold:
            logger.debug(
                f"[ModMatcher] Match mod installé trouvé pour '{query}': '{best_mod.title}' "
                f"(score={best_score:.2f} >= {min_threshold})"
            )
            return best_mod, best_score

        return None
