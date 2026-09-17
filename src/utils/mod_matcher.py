"""
Utility for scoring similarity between mod dependency requirements and catalog / installed mods.
Uses TitleNormalizer for regex stripping, tokenization, and accent removal.
"""
import difflib
import re
from typing import Optional, List, Tuple, Any

from src.utils.logger import logger
from src.utils.title_normalizer import TitleNormalizer


class ModMatcher(TitleNormalizer):
    """
    Scoring and similarity engine for matching parent mod requirements
    against catalog and locally installed mods.
    """

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

        if q_clean.lower() in cls.GENERIC_EXCLUDED_WORDS or len(q_clean) < 2:
            return 0.0

        # 1. Exact match on cleaned core names
        if q_clean == c_clean:
            return 1.0

        # 2. Exact match on canonical alphanumeric fingerprints (ignores hyphens, underscores, glued words)
        q_fp = cls.canonical_fingerprint(q_clean)
        c_fp = cls.canonical_fingerprint(c_clean)
        if q_fp and c_fp and q_fp == c_fp:
            return 1.0

        q_tokens = cls.get_significant_tokens(q_clean)
        c_tokens = cls.get_significant_tokens(c_clean)

        if not q_tokens or not c_tokens:
            return 0.0

        # Token sort check: insensitive to word permutations (e.g. "Career Mod Kuttoe" vs "Kuttoe Career Mod")
        sorted_q = " ".join(sorted(q_tokens))
        sorted_c = " ".join(sorted(c_tokens))
        if sorted_q == sorted_c:
            return 0.98

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
            extracted_author, _ = cls.extract_author_and_version(candidate_title)
            effective_author = (candidate_author or extracted_author or "").strip().lower()
            author_tokens = set(cls.get_significant_tokens(effective_author)) if effective_author else set()
            if author_tokens and set(missing_from_candidate) <= author_tokens:
                return 0.95
            overlap = len(q_set.intersection(c_set)) / len(q_set)
            return round(0.40 * overlap, 3)

        # 2. Token containment (all query tokens are present in candidate, e.g. 'xml injector' in 'scumbumbo xml injector')
        if q_set.issubset(c_set):
            ratio = len(q_set) / max(len(c_set), 1)
            extra = diff_c - {"mod", "mods"}
            extracted_author, _ = cls.extract_author_and_version(candidate_title)
            if not extra or (candidate_author and extra <= {candidate_author.lower()}) or (extracted_author and extra <= {extracted_author.lower()}):
                return 0.95
            # Guard against 1-token generic queries matching long mod titles
            if len(q_set) == 1 and ratio < 0.5:
                return round(0.40 * ratio, 3)
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

        # Fuzzy similarity incorporating token-sort sequence matching
        if intersection and len(intersection) >= len(q_tokens) * 0.75:
            str_ratio = max(
                difflib.SequenceMatcher(None, q_clean, c_clean).ratio(),
                difflib.SequenceMatcher(None, sorted_q, sorted_c).ratio(),
            )
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
        """
        from src.database.models import CatalogMod

        if not query:
            return None

        # Direct remote_id check if query is digits
        if str(query).isdigit():
            direct_id = session.query(CatalogMod).filter_by(remote_id=str(query)).first()
            if direct_id:
                return direct_id, 1.0

        q_clean = cls.clean_mod_title(query)
        if not q_clean or len(q_clean) < 2 or q_clean.lower() in cls.GENERIC_EXCLUDED_WORDS:
            return None

        dynamic_threshold = cls.get_dynamic_threshold(query, min_threshold)
        tokens = cls.get_significant_tokens(q_clean)

        # Filter out stopwords and prioritize longest/most specific tokens for SQL pre-selection
        informative_tokens = [tok for tok in tokens if tok.lower() not in cls.STOP_WORDS and len(tok) >= 3]
        if not informative_tokens:
            informative_tokens = [tok for tok in tokens if len(tok) >= 2]
        informative_tokens.sort(key=len, reverse=True)

        candidate_query = session.query(CatalogMod)
        if informative_tokens:
            from sqlalchemy import or_
            token_filters = [CatalogMod.title.ilike(f"%{tok}%") for tok in informative_tokens[:3]]
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

        if best_mod and best_score >= dynamic_threshold:
            logger.debug(
                f"[ModMatcher] Match catalog trouvé pour '{query}': '{best_mod.title}' "
                f"(score={best_score:.2f} >= {dynamic_threshold:.2f})"
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
        """
        if not query or not installed_mods:
            return None

        q_clean = cls.clean_mod_title(query)
        if not q_clean or len(q_clean) < 2 or q_clean.lower() in cls.GENERIC_EXCLUDED_WORDS:
            return None

        dynamic_threshold = cls.get_dynamic_threshold(query, min_threshold)

        best_mod = None
        best_score = 0.0

        for im in installed_mods:
            im_title = getattr(im, "title", "") or ""
            im_folder = getattr(im, "folder_name", "") or ""

            candidates = [im_title]
            if im_folder:
                candidates.append(im_folder)

            files_list = []
            if hasattr(im, "get_installed_files_list"):
                try:
                    files_list = im.get_installed_files_list() or []
                except Exception:
                    files_list = []
            elif hasattr(im, "installed_files") and isinstance(im.installed_files, list):
                files_list = im.installed_files

            for fpath in files_list[:15]:
                fname = fpath.replace("\\", "/").split("/")[-1]
                f_base = re.sub(r"\.(?:package|ts4script)$", "", fname, flags=re.I)
                if f_base:
                    candidates.append(f_base)

            im_best = 0.0
            for cand in candidates:
                if not cand:
                    continue
                score = cls.match_score(query, cand)
                if score > im_best:
                    im_best = score

            if im_best > best_score:
                best_score = im_best
                best_mod = im

        if best_mod and best_score >= dynamic_threshold:
            logger.debug(
                f"[ModMatcher] Match mod installé trouvé pour '{query}': '{best_mod.title}' "
                f"(score={best_score:.2f} >= {dynamic_threshold:.2f})"
            )
            return best_mod, best_score

        return None
