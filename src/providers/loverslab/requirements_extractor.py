"""
RequirementsExtractor: Heuristic and regex-based extraction of prerequisites
and dependencies for LoversLab mods.
"""

import copy
import re
import urllib.parse
from typing import Dict, List, Any, Tuple, Optional
from bs4 import BeautifulSoup

from src.providers.loverslab.matchers import is_wickedwhims_name, is_nisa_name
from src.utils.game_dlc_matcher import GameDlcMatcher, SIMS4_PREFIX_REGEX
from src.utils.mod_matcher import ModMatcher

KNOWN_MOD_ALIASES: Dict[str, Dict[str, str]] = {
    "wickedwhims": {
        "remote_id": "3169",
        "title": "WickedWhims",
        "url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
    },
    "wicked whims": {
        "remote_id": "3169",
        "title": "WickedWhims",
        "url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
    },
    "ww": {
        "remote_id": "3169",
        "title": "WickedWhims",
        "url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
    },
    "nisa's wicked perversion": {
        "remote_id": "9443",
        "title": "Nisa's Wicked Perversions",
        "url": "https://www.loverslab.com/files/file/9443-nisas-wicked-perversions/",
    },
    "nisas wicked perversion": {
        "remote_id": "9443",
        "title": "Nisa's Wicked Perversions",
        "url": "https://www.loverslab.com/files/file/9443-nisas-wicked-perversions/",
    },
    "nisa's wicked perversions": {
        "remote_id": "9443",
        "title": "Nisa's Wicked Perversions",
        "url": "https://www.loverslab.com/files/file/9443-nisas-wicked-perversions/",
    },
    "nisas wicked perversions": {
        "remote_id": "9443",
        "title": "Nisa's Wicked Perversions",
        "url": "https://www.loverslab.com/files/file/9443-nisas-wicked-perversions/",
    },
    "nwp": {
        "remote_id": "9443",
        "title": "Nisa's Wicked Perversions",
        "url": "https://www.loverslab.com/files/file/9443-nisas-wicked-perversions/",
    },
}

HEADER_RE = re.compile(r"(?i)^(requirements?|pr[ée]requis|prerequisites?|needs?|required\s*mods?)\s*:?$")


def extract_loverslab_requirements(
    soup: BeautifulSoup,
    known_aliases: Optional[Dict[str, Dict[str, str]]] = None,
) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
    """
    Extracts Requirements field from the mod info panel (.cFileInfo / .ipsDataList).
    Handles multi-requirement delimiter splitting (-, +, ,, /, &, et, and),
    resolves known LoversLab aliases, and returns individual required mod items.
    Returns (requirements_text, requirements_status, requirements_mods_list).
    """
    aliases = known_aliases if known_aliases is not None else KNOWN_MOD_ALIASES

    req_item = None
    for li in soup.select(".cFileInfo li, .cFileView li, .ipsDataList li"):
        title_span = li.select_one(".ipsDataItem_size3, strong")
        if title_span and "require" in title_span.get_text().lower():
            req_item = li
            break

    if not req_item:
        return None, "NONE", []

    data_el = req_item.select_one(".cFileInfoData, .ipsDataItem_generic:not(.ipsDataItem_size3)")
    if not data_el:
        return None, "NONE", []

    # Preserve line breaks across <br>, <p>, <div>, <li>
    data_el_copy = copy.copy(data_el)
    for tag in data_el_copy.find_all(["br", "p", "div", "li"]):
        tag.replace_with("\n" + tag.get_text() + "\n")

    raw_text = data_el_copy.get_text(separator="\n", strip=True)
    raw_text = re.sub(r"[ \t]+", " ", raw_text)
    raw_text = re.sub(r"\n\s*\n+", "\n", raw_text).strip()

    # Exclude base game mentions
    is_base_game = bool(
        re.fullmatch(
            r"(?i)\s*(sims\s*4|the\s*sims\s*4|base\s*game|jeu\s*de\s*base|sims\s*4\s*base\s*game|none|aucun|aucun[e]?|n/?a|-)\s*",
            raw_text,
        )
    )
    if not raw_text or is_base_game:
        return raw_text, "NONE", []

    seen_ids = set()
    seen_titles = set()
    req_mods: List[Dict[str, Any]] = []

    # 1. Parse explicit links inside data element
    for a in data_el.find_all("a", href=True):
        href = a.get("href", "")
        m = re.search(r"/files/file/(\d+)-?([^/?#]*)", href)
        if m:
            r_id = m.group(1)
            slug = m.group(2)
            if r_id not in seen_ids:
                seen_ids.add(r_id)
                t_name = a.get_text(strip=True) or urllib.parse.unquote(slug).replace("-", " ").title()
                seen_titles.add(t_name.lower())
                clean_slug = urllib.parse.unquote(slug)
                req_mods.append(
                    {
                        "source": "loverslab",
                        "remote_id": r_id,
                        "title": t_name,
                        "url": f"https://www.loverslab.com/files/file/{r_id}-{clean_slug}/",
                    }
                )

    for m in re.finditer(r"https?://(?:www\.)?loverslab\.com/files/file/(\d+)-?([^/\s\"'>]*)", str(data_el)):
        r_id = m.group(1)
        slug = m.group(2)
        if r_id not in seen_ids:
            seen_ids.add(r_id)
            clean_slug = urllib.parse.unquote(slug)
            t_name = clean_slug.replace("-", " ").title()
            seen_titles.add(t_name.lower())
            req_mods.append(
                {
                    "source": "loverslab",
                    "remote_id": r_id,
                    "title": t_name,
                    "url": f"https://www.loverslab.com/files/file/{r_id}-{clean_slug}/",
                }
            )

    # 2. Extract textual candidates
    text_without_urls = re.sub(r"https?://\S+", "", raw_text)
    raw_lines = [line_str.strip() for line_str in text_without_urls.splitlines() if line_str.strip()]

    candidate_tokens: List[str] = []
    for line in raw_lines:
        clean_line = re.sub(r"^[\s•\*\-\–\—\d\.\)\:]+\s*", "", line).strip()
        if not clean_line or len(clean_line) < 2:
            continue

        if HEADER_RE.match(clean_line):
            continue

        # Strip leading requirement labels
        unprefixed_line = re.sub(
            r"(?i)^(?:requirements?|pr[ée]requis|prerequisites?|needs?|required(?:\s*(?:mods?|packs?|dlcs?))?|requires?|dlcs?|packs?)\s*[:\-–—\s]\s*",
            "",
            clean_line,
        ).strip()

        has_delimiters = bool(re.search(r"[,;+/|]|\s+[-–—]\s*|\s+(?:and|et)\s+", unprefixed_line))
        is_sentence = (
            bool(re.search(r"(?i)\b(is|are|does|do|will|have|has|enabled)\b", unprefixed_line)) and not has_delimiters
        )

        if is_sentence:
            line_tokens = [unprefixed_line]
        else:
            protected_line = re.sub(r"(?i)\bcats\s*(?:&|and)\s*dogs\b", "Cats_and_Dogs", unprefixed_line)
            protected_line = re.sub(r"(?i)\blife\s*(?:&|and)\s*death\b", "Life_and_Death", protected_line)
            protected_line = re.sub(
                r"(?i)\b(sims\s*4|ts4)\s*[-–—]\s*",
                r"\1 : ",
                protected_line,
            )
            primary_tokens = re.split(r"[,;+/|]|\s+[-–—]\s*|\s+(?:and|et|as\s+well\s+as)\s+|\s+&\s+", protected_line)
            line_tokens = []
            for pt in primary_tokens:
                pt_str = pt.replace("Cats_and_Dogs", "Cats & Dogs").replace("Life_and_Death", "Life & Death").strip()
                if not pt_str:
                    continue
                sub_parts = re.split(r"(\s+[a-zA-Z0-9]+)-(?=[A-Z])", pt_str)
                if len(sub_parts) > 1:
                    reconstructed = []
                    curr = sub_parts[0]
                    for i in range(1, len(sub_parts), 2):
                        curr += sub_parts[i]
                        reconstructed.append(curr.strip())
                        curr = sub_parts[i + 1] if i + 1 < len(sub_parts) else ""
                    if curr.strip():
                        reconstructed.append(curr.strip())
                    line_tokens.extend(reconstructed)
                else:
                    line_tokens.append(pt_str)

        for lt in line_tokens:
            lt_clean = lt.strip().strip("\"'`").rstrip(".")
            if lt_clean and len(lt_clean) >= 2:
                candidate_tokens.append(lt_clean)

    # 3. Classify and resolve candidate tokens
    for candidate in candidate_tokens:
        if not candidate or len(candidate) < 2:
            continue

        cand_clean = re.sub(r"^[\s•\*\-\–\—\d\.\)\:\[\]\(\)\{\}\"\'\`]+", "", candidate).strip()
        cand_clean = re.sub(
            r"(?i)^(?:requirements?|pr[ée]requis|prerequisites?|needs?|required(?:\s*(?:mods?|packs?|dlcs?))?|requires?|dlcs?|packs?)\s*[:\-–—\s]\s*",
            "",
            cand_clean,
        ).strip()

        if not cand_clean or cand_clean.lower() in ModMatcher.GENERIC_EXCLUDED_WORDS:
            continue

        # Check if candidate refers to base game
        is_cand_bg = GameDlcMatcher.is_base_game_only(cand_clean) or bool(
            re.search(r"(?i)\bthe\s+sims\s+4\b", cand_clean)
            and re.search(r"(?i)\b(?:pc|mac|base\s*game|jeu\s*de\s*base)\b", cand_clean)
        )
        if is_cand_bg:
            bg_title = "The Sims 4 (Jeu de base)"
            if "the sims 4" not in [x.get("title", "").lower() for x in req_mods]:
                seen_titles.add(bg_title.lower())
                req_mods.append(
                    {
                        "source": "game_dlc",
                        "remote_id": "BASE_GAME",
                        "title": bg_title,
                        "url": "",
                        "is_game_dlc": True,
                        "dlc_name": "Jeu de base",
                        "is_installed": True,
                    }
                )
            continue

        c_starts_sims4 = bool(SIMS4_PREFIX_REGEX.match(cand_clean.strip()))
        is_dlc, pack_name, pack_code = GameDlcMatcher.match_dlc(cand_clean)
        if is_dlc or c_starts_sims4:
            pack_name = (
                pack_name
                or re.sub(
                    r"^(?:(?:the|les|die|los|i|gli|de|os)\s*)?sims(?:™|®)?\s*4\s*[:\-–—]?\s*",
                    "",
                    cand_clean,
                    flags=re.IGNORECASE,
                ).strip()
            )
            dlc_key = (pack_code or pack_name or cand_clean).lower()
            if dlc_key not in seen_titles:
                seen_titles.add(dlc_key)
                req_mods.append(
                    {
                        "source": "game_dlc",
                        "remote_id": pack_code or "",
                        "title": f"The Sims 4 : {pack_name}"
                        if not cand_clean.lower().startswith("the sims 4")
                        else cand_clean,
                        "url": "",
                        "is_game_dlc": True,
                        "dlc_name": pack_name,
                        "dlc_code": pack_code,
                    }
                )
            continue

        c_lower = candidate.lower()

        if is_wickedwhims_name(candidate):
            alias_info = {
                "remote_id": "3169",
                "title": "WickedWhims",
                "url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
            }
        elif is_nisa_name(candidate):
            alias_info = {
                "remote_id": "9443",
                "title": "Nisa's Wicked Perversions",
                "url": "https://www.loverslab.com/files/file/9443-nisas-wicked-perversions/",
            }
        else:
            c_cleaned = ModMatcher.clean_mod_title(candidate)
            alias_info = aliases.get(c_lower) or aliases.get(c_cleaned)

        if alias_info:
            r_id = alias_info["remote_id"]
            if r_id not in seen_ids:
                seen_ids.add(r_id)
                seen_titles.add(alias_info["title"].lower())
                req_mods.append(
                    {
                        "source": "loverslab",
                        "remote_id": r_id,
                        "title": alias_info["title"],
                        "url": alias_info["url"],
                    }
                )
            continue

        is_duplicate = False
        for existing in req_mods:
            e_title = existing["title"]
            if ModMatcher.match_score(candidate, e_title) >= 0.85:
                is_duplicate = True
                break
            if c_lower == e_title.lower():
                is_duplicate = True
                break
        if is_duplicate:
            continue

        if c_lower not in seen_titles:
            seen_titles.add(c_lower)
            req_mods.append(
                {
                    "source": "loverslab",
                    "remote_id": "",
                    "title": candidate,
                    "url": "",
                }
            )

    if req_mods:
        if all((bool(m.get("remote_id")) and m.get("remote_id") != "") or m.get("is_game_dlc") for m in req_mods):
            status = "RESOLVED"
        else:
            status = "PENDING_VERIFICATION"
    else:
        status = "NONE"

    return raw_text, status, req_mods
