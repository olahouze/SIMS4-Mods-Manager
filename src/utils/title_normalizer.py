"""
Title normalization rules, regex extractors, accent strippers, and token utilities for Sims 4 mod titles.
"""

import re
import unicodedata
from typing import Optional, List, Tuple


class TitleNormalizer:
    """
    Handles regex-based stripping, token extraction, accents removal,
    and fingerprint generation for mod titles.
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

    # Generic header / noise words that must never be considered valid mod titles
    GENERIC_EXCLUDED_WORDS = {
        "requirements",
        "requirement",
        "prerequisites",
        "prerequisite",
        "download",
        "downloads",
        "dependencies",
        "dependency",
        "optional",
        "optionnel",
        "requis",
        "prérequis",
        "prerequis",
        "links",
        "link",
        "lien",
        "liens",
        "none",
        "aucun",
        "aucune",
        "n/a",
        "na",
        "install",
        "installation",
        "info",
        "notes",
        "note",
        "objects",
        "object",
        "tuning",
        "tunings",
        "strings",
        "string",
        "cas assets",
        "assets",
        "asset",
        "xml resources",
        "resources",
        "resource",
        "framework",
        "library",
        "libraries",
        "third-party",
        "third party",
        "party library",
        "no third",
        "package",
        "packages",
        "script",
        "scripts",
        "script-only",
    }

    # Common English & French grammatical stop words to ignore during token prioritization
    STOP_WORDS = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "for",
        "with",
        "in",
        "on",
        "at",
        "by",
        "from",
        "to",
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "du",
        "de",
        "d",
        "et",
        "ou",
        "pour",
        "avec",
        "dans",
        "par",
    }

    @classmethod
    def get_dynamic_threshold(cls, query: str, base_threshold: float = 0.70) -> float:
        """Dynamically adjusts the minimum matching threshold based on significant tokens."""
        if not query:
            return base_threshold
        q_clean = cls.clean_mod_title(query)
        tokens = cls.get_significant_tokens(q_clean)
        informative = [t for t in tokens if t.lower() not in cls.STOP_WORDS]
        count = len(informative) if informative else len(tokens)
        if count <= 1:
            return max(base_threshold, 0.95)
        elif count == 2:
            return max(base_threshold, 0.85)
        return base_threshold

    @classmethod
    def split_camel_case(cls, text: str) -> str:
        """Splits PascalCase/camelCase into separated words while preserving acronyms."""
        if not text:
            return ""
        s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
        s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
        return s

    @classmethod
    def canonical_fingerprint(cls, text: str) -> str:
        """Generates a normalized alphanumeric fingerprint for comparison."""
        if not text:
            return ""
        s = cls.strip_accents(text).lower()
        return re.sub(r"[^a-z0-9]", "", s)

    @classmethod
    def strip_accents(cls, text: str) -> str:
        """Removes diacritical marks/accents from text."""
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    @classmethod
    def extract_author_and_version(cls, title: str) -> Tuple[Optional[str], Optional[str]]:
        """Attempts to extract creator name and version from bracketed or prefixed patterns."""
        if not title:
            return None, None

        author = None
        version = None

        m_author = re.match(r"^\s*\[([a-zA-Z0-9_\-\s]{2,30})\]", title)
        if m_author:
            candidate = m_author.group(1).strip()
            if not re.match(r"(?i)^(?:ts4|sims\s*4|mod|wip|public|v\d+)", candidate):
                author = candidate
        else:
            m_by = cls.CREATOR_SUFFIX_PATTERN.search(title)
            if m_by:
                by_text = m_by.group(0).strip()
                parts = by_text.split()
                if len(parts) >= 2:
                    author = parts[-1]
            else:
                m_dash = cls.CREATOR_DASH_PREFIX_PATTERN.match(title)
                if m_dash:
                    author = re.sub(r"\s*[-–:]\s*$", "", m_dash.group(0)).strip()

        m_ver = cls.VERSION_PATTERN.search(title)
        if m_ver:
            version = m_ver.group(0).strip()

        return author, version

    @classmethod
    def clean_mod_title(cls, title: str) -> str:
        """Extracts the essential core name of a mod by stripping creator tags, version, and dates."""
        if not title:
            return ""

        cleaned = cls.ANY_BRACKETS_PATTERN.sub(" ", title)
        cleaned = cleaned.replace("_", " ")
        cleaned = re.sub(r"(?<=\w)-(?=\w)", " ", cleaned)
        cleaned = cls.DATE_PATTERN.sub(" ", cleaned)
        cleaned = cls.VERSION_PATTERN.sub(" ", cleaned)
        cleaned = cls.CREATOR_SUFFIX_PATTERN.sub(" ", cleaned)
        cleaned = cls.CREATOR_PREFIX_PATTERN.sub(" ", cleaned)
        cleaned = cls.CREATOR_DASH_PREFIX_PATTERN.sub(" ", cleaned)
        cleaned = cls.NOISE_WORDS_PATTERN.sub(" ", cleaned)
        cleaned = cls.strip_accents(cleaned)
        cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()

        if len(cleaned.split()) > 1:
            cleaned = re.sub(r"\s+\bmod\b$", "", cleaned).strip()

        if not cleaned:
            fallback = re.sub(r"[^a-zA-Z0-9\s]", " ", cls.strip_accents(title))
            cleaned = re.sub(r"\s+", " ", fallback).strip().lower()

        return cleaned

    @classmethod
    def get_significant_tokens(cls, cleaned_text: str) -> List[str]:
        """Returns sorted non-trivial words (length >= 2) from cleaned text."""
        return [w for w in cleaned_text.split() if len(w) >= 2]
