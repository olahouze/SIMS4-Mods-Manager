import copy
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Callable
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from src.providers.base import BaseSourceProvider
from src.providers.patreon import PatreonProvider
from src.providers.loverslab.downloader import download_loverslab_file, extract_download_candidates as _ext_dl_candidates
from src.providers.loverslab.matchers import is_wickedwhims_name, is_nisa_name
from src.providers.loverslab.parsers import extract_gallery_screenshots, sanitize_description_html
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.utils.logger import logger
from src.utils.mod_matcher import ModMatcher


class LoversLabProvider(BaseSourceProvider):
    """
    Provider for scraping LoversLab The Sims 4 files category (161),
    extracting attachments, adult content handling, and identifying external/Patreon links.
    """

    provider_name = "loverslab"
    display_name = "LoversLab"
    base_url = "https://www.loverslab.com"
    category_url = "https://www.loverslab.com/files/category/161-the-sims-4/"

    CATEGORIES = [
        {
            "id": "174",
            "name": "WickedWhims",
            "slug": "174-wickedwhims",
            "url": "https://www.loverslab.com/files/category/174-wickedwhims/",
            "default_pages": 16,
        },
        {
            "id": "201",
            "name": "Animations - WickedWhims",
            "slug": "201-animations-wickedwhims",
            "url": "https://www.loverslab.com/files/category/201-animations-wickedwhims/",
            "default_pages": 7,
        },
        {
            "id": "215",
            "name": "Translations - WickedWhims",
            "slug": "215-translations-wickedwhims",
            "url": "https://www.loverslab.com/files/category/215-translations-wickedwhims/",
            "default_pages": 5,
        },
        {
            "id": "202",
            "name": "Animations - Other",
            "slug": "202-animations-other",
            "url": "https://www.loverslab.com/files/category/202-animations-other/",
            "default_pages": 7,
        },
        {
            "id": "200",
            "name": "Extensions",
            "slug": "200-extensions",
            "url": "https://www.loverslab.com/files/category/200-extensions/",
            "default_pages": 3,
        },
        {
            "id": "203",
            "name": "Clothing",
            "slug": "203-clothing",
            "url": "https://www.loverslab.com/files/category/203-clothing/",
            "default_pages": 128,
        },
        {
            "id": "204",
            "name": "Accessories & Makeup",
            "slug": "204-accessories-makeup",
            "url": "https://www.loverslab.com/files/category/204-accessories-makeup/",
            "default_pages": 16,
        },
        {
            "id": "205",
            "name": "Body Parts",
            "slug": "205-body-parts",
            "url": "https://www.loverslab.com/files/category/205-body-parts/",
            "default_pages": 12,
        },
        {
            "id": "206",
            "name": "Objects",
            "slug": "206-objects",
            "url": "https://www.loverslab.com/files/category/206-objects/",
            "default_pages": 86,
        },
        {
            "id": "404",
            "name": "Paintings & Posters",
            "slug": "404-paintings-posters",
            "url": "https://www.loverslab.com/files/category/404-paintings-posters/",
            "default_pages": 14,
        },
        {
            "id": "207",
            "name": "Lots",
            "slug": "207-lots",
            "url": "https://www.loverslab.com/files/category/207-lots/",
            "default_pages": 18,
        },
        {
            "id": "209",
            "name": "Translations",
            "slug": "209-translations",
            "url": "https://www.loverslab.com/files/category/209-translations/",
            "default_pages": 35,
        },
        {
            "id": "210",
            "name": "Other",
            "slug": "210-other",
            "url": "https://www.loverslab.com/files/category/210-other/",
            "default_pages": 23,
        },
        {
            "id": "216",
            "name": "Uncategorized",
            "slug": "216-uncategorized",
            "url": "https://www.loverslab.com/files/category/216-uncategorized/",
            "default_pages": 27,
        },
    ]

    KNOWN_MOD_ALIASES = {
        "ww": {
            "remote_id": "3169",
            "title": "WickedWhims",
            "url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
        },
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
        "wicked-whims": {
            "remote_id": "3169",
            "title": "WickedWhims",
            "url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
        },
        "wicked_whims": {
            "remote_id": "3169",
            "title": "WickedWhims",
            "url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
        },
        "nwp": {
            "remote_id": "9443",
            "title": "Nisa's Wicked Perversions",
            "url": "https://www.loverslab.com/files/file/9443-nisas-wicked-perversions/",
        },
        "nisa": {
            "remote_id": "9443",
            "title": "Nisa's Wicked Perversions",
            "url": "https://www.loverslab.com/files/file/9443-nisas-wicked-perversions/",
        },
        "nisas wicked perversions": {
            "remote_id": "9443",
            "title": "Nisa's Wicked Perversions",
            "url": "https://www.loverslab.com/files/file/9443-nisas-wicked-perversions/",
        },
        "nisa's wicked perversions": {
            "remote_id": "9443",
            "title": "Nisa's Wicked Perversions",
            "url": "https://www.loverslab.com/files/file/9443-nisas-wicked-perversions/",
        },
    }

    def __init__(self):
        self.patreon_provider = PatreonProvider()
        self._category_pages_cache: Dict[str, int] = {c["id"]: c["default_pages"] for c in self.CATEGORIES}
        self.current_category_info: str = "WickedWhims"

    def update_category_detected_pages(self, cat_id: str, detected_pages: int) -> None:
        if detected_pages > 0:
            self._category_pages_cache[cat_id] = detected_pages

    def _get_category_page_counts(self) -> List[Tuple[Dict[str, Any], int]]:
        return [(c, self._category_pages_cache.get(c["id"], c["default_pages"])) for c in self.CATEGORIES]

    def get_total_pages(self) -> int:
        return sum(self._category_pages_cache.get(c["id"], c["default_pages"]) for c in self.CATEGORIES)

    def _resolve_category_page(self, global_page: int) -> Tuple[Dict[str, Any], int, int]:
        counts = self._get_category_page_counts()
        remaining = global_page
        for cat, num_pages in counts:
            if remaining <= num_pages:
                return cat, remaining, num_pages
            remaining -= num_pages

        last_cat, last_pages = counts[-1]
        return last_cat, max(1, remaining), last_pages

    def scrape_category_page(
        self, category: Dict[str, Any], page: int = 1, limit: int = 25
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        cat_url = category["url"].rstrip("/") + "/"
        url = cat_url if page == 1 else f"{cat_url}page/{page}/"
        session = SessionManager.get_http_session("loverslab")

        if ShutdownManager.is_shutting_down():
            return [], 0

        logger.info(f"Scraping LoversLab [{category['name']}] page {page}: {url}")
        results: List[Dict[str, Any]] = []
        detected_pages: Optional[int] = None

        try:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"LoversLab request returned status {resp.status_code} for {url}")
                return results, detected_pages

            soup = BeautifulSoup(resp.text, "html.parser")

            if page == 1:
                pag = soup.select_one("[data-pages]")
                if pag and pag.get("data-pages"):
                    try:
                        detected_pages = int(pag["data-pages"])
                    except Exception:
                        pass
                if not detected_pages:
                    p_nums = []
                    for a in soup.select("ul.ipsPagination a[href*='/page/']"):
                        m = re.search(r"/page/(\d+)", a.get("href", ""))
                        if m:
                            p_nums.append(int(m.group(1)))
                    if p_nums:
                        detected_pages = max(p_nums)

                if detected_pages:
                    self.update_category_detected_pages(category["id"], detected_pages)

            items = soup.select("li.ipsDataItem, li[data-rowid]")

            for item in items:
                title_elem = item.select_one(
                    ".ipsDataItem_title a[href*='/files/file/'], "
                    "h4.ipsDataItem_title a, "
                    ".ipsDataItem_title a, "
                    "h4 a[href*='/files/file/']"
                )
                if not title_elem or not title_elem.get("href"):
                    title_elem = item.select_one("a[href*='/files/file/']")
                if not title_elem or not title_elem.get("href"):
                    continue

                page_url = title_elem["href"]
                if "files/file/" not in page_url:
                    continue

                remote_id_match = re.search(r"/files/file/(\d+)", page_url)
                remote_id = remote_id_match.group(1) if remote_id_match else page_url

                title = title_elem.get_text(strip=True) if title_elem else ""
                title = title.replace("\u200b", "").replace("\ufeff", "").strip()
                if title in ["''", '""']:
                    title = ""

                if not title and title_elem and title_elem.get("title"):
                    raw_title = title_elem["title"]
                    cleaned = re.sub(
                        r'^(View the file\s*|More information about\s*["\'\\]?)', "", raw_title, flags=re.IGNORECASE
                    )
                    cleaned = re.sub(r'["\'\\]?\s*$', "", cleaned)
                    title = cleaned.replace("\u200b", "").replace("\ufeff", "").strip()

                if not title or title in ["''", '""']:
                    slug_match = re.search(r"/files/file/\d+-([^/]+)", urllib.parse.unquote(page_url))
                    if slug_match:
                        title = (
                            slug_match.group(1)
                            .replace("-", " ")
                            .replace("—", "-")
                            .replace("\u200b", "")
                            .replace("\ufeff", "")
                            .strip()
                            .title()
                        )
                    else:
                        title = f"Mod LoversLab #{remote_id}"

                author_elem = item.select_one(".ipsDataItem_author, a[data-ipshover]")
                author = author_elem.get_text(strip=True) if author_elem else "Inconnu"
                author = author.replace("\u200b", "").replace("\ufeff", "").strip()

                thumbnail_url = ""
                thumb_elem = item.select_one(
                    "img.ipsItem_coverImage, img[data-src], img[src*='monthly_'], img[src*='uploads/'], img"
                )
                if thumb_elem:
                    thumbnail_url = (
                        thumb_elem.get("data-src") or thumb_elem.get("data-loaded-src") or thumb_elem.get("src") or ""
                    )

                if not thumbnail_url:
                    cover_elem = item.select_one("[style*='background-image'], .cFileView_cover, .ipsCoverImage")
                    if cover_elem and cover_elem.get("style"):
                        bg_match = re.search(r'url\(["\'\\]?([^"\'\\)]+)["\'\\]?\)', cover_elem["style"])
                        if bg_match:
                            thumbnail_url = bg_match.group(1)

                if thumbnail_url:
                    if thumbnail_url.startswith("//"):
                        thumbnail_url = "https:" + thumbnail_url
                    elif thumbnail_url.startswith("/"):
                        thumbnail_url = self.base_url + thumbnail_url

                time_elem = item.select_one("time[datetime]")
                updated_date = None
                if time_elem and time_elem.get("datetime"):
                    try:
                        updated_date = date_parser.parse(time_elem["datetime"]).replace(tzinfo=None)
                    except Exception:
                        logger.debug(f"Could not parse date for item {remote_id}: {time_elem.get('datetime')}")

                tags = [t.get_text(strip=True) for t in item.select(".ipsBadge, .ipsTag") if t.get_text(strip=True)]
                if category["name"] not in tags:
                    tags.append(category["name"])

                logger.debug(f"LoversLab item found: '{title}' (ID: {remote_id}, thumb: {bool(thumbnail_url)})")

                results.append(
                    {
                        "source": self.provider_name,
                        "remote_id": remote_id,
                        "title": title,
                        "author": author,
                        "category": category["name"],
                        "tags": tags,
                        "page_url": page_url,
                        "thumbnail_url": thumbnail_url,
                        "updated_date": updated_date,
                        "published_date": updated_date,
                        "patreon_status": "NONE",
                        "patreon_tier": "",
                    }
                )

            if results:

                def _inspect_item_target(entry: Dict[str, Any]) -> Dict[str, Any]:
                    p_url = entry["page_url"]
                    dl_chk = p_url.rstrip("/") + "/?do=download"
                    try:
                        r_chk = session.get(dl_chk, allow_redirects=False, timeout=6)
                        loc = r_chk.headers.get("Location", "")
                        if r_chk.status_code in [301, 302, 303, 307, 308] and "patreon.com" in loc.lower():
                            pat_info = self.patreon_provider.check_post_access(loc)
                            entry["patreon_status"] = pat_info.get("status", "PUBLIC")
                            entry["patreon_tier"] = pat_info.get("tier_str", "")
                            if "Patreon" not in entry["tags"]:
                                entry["tags"].append("Patreon")
                        else:
                            entry["patreon_status"] = "NONE"
                    except Exception:
                        entry["patreon_status"] = "NONE"
                    return entry

                if ShutdownManager.is_shutting_down():
                    return results, detected_pages

                try:
                    with ThreadPoolExecutor(max_workers=min(len(results), 6)) as pool:
                        results = list(pool.map(_inspect_item_target, results))
                except RuntimeError as r_err:
                    if "interpreter shutdown" in str(r_err).lower() or ShutdownManager.is_shutting_down():
                        return results, detected_pages
                    raise

            logger.info(f"LoversLab [{category['name']}] p.{page} scraping finished: {len(results)} mods.")

        except Exception as e:
            if ShutdownManager.is_shutting_down() or "interpreter shutdown" in str(e).lower():
                return results, detected_pages
            logger.error(f"Error while scraping LoversLab category {category['name']} page {page}: {e}", exc_info=True)

        return results, detected_pages

    def scrape_catalog(self, page: int = 1, limit: int = 25) -> List[Dict[str, Any]]:
        cat, local_page, total_cat_pages = self._resolve_category_page(page)
        self.current_category_info = f"{cat['name']} (p. {local_page}/{total_cat_pages})"
        results, _ = self.scrape_category_page(cat, local_page, limit)
        return results

    def get_mod_details(self, mod_url: str) -> Dict[str, Any]:
        session = SessionManager.get_http_session("loverslab")
        details: Dict[str, Any] = {
            "description": "",
            "download_urls": [],
            "external_links": [],
            "patreon_status": "NONE",
            "patreon_tier": "",
            "version_str": "",
            "requirements_text": None,
            "requirements_status": "NONE",
            "requirements_mods": [],
            "screenshots": [],
        }

        try:
            resp = session.get(mod_url, timeout=20)
            if resp.status_code != 200:
                return details

            soup = BeautifulSoup(resp.text, "html.parser")

            direct_dl_url = f"{mod_url.rstrip('/')}/?do=download"
            is_direct_download = False
            patreon_redirect_url = None

            try:
                r_chk = session.get(direct_dl_url, allow_redirects=False, timeout=8)
                if r_chk.status_code in [301, 302, 303, 307, 308]:
                    loc = r_chk.headers.get("Location", "")
                    if "patreon.com" in loc.lower():
                        patreon_redirect_url = loc
                    elif loc:
                        if loc not in details["external_links"]:
                            details["external_links"].append(loc)
                elif r_chk.status_code in [200, 403]:
                    is_direct_download = True
                    details["download_urls"].append(
                        {
                            "name": "Téléchargement LoversLab (Direct)",
                            "url": direct_dl_url,
                            "size": 0,
                        }
                    )
            except Exception as e:
                logger.debug(f"Redirect check error for {direct_dl_url}: {e}")

            if patreon_redirect_url:
                if patreon_redirect_url not in details["external_links"]:
                    details["external_links"].append(patreon_redirect_url)
                pat_info = self.patreon_provider.check_post_access(patreon_redirect_url)
                details["patreon_status"] = pat_info.get("status", "LOCKED")
                details["patreon_tier"] = pat_info.get("tier_str", "")
                if pat_info.get("download_urls"):
                    details["download_urls"].extend(pat_info["download_urls"])
                else:
                    details["download_urls"].append(
                        {
                            "name": "Post Patreon (Téléchargement)",
                            "url": patreon_redirect_url,
                            "size": 0,
                        }
                    )

            gallery_screenshots: List[str] = extract_gallery_screenshots(soup, self.base_url)

            content_elem = soup.select_one(
                "article div.ipsType_richText, .cFileView_content div.ipsType_richText, [data-role='commentContent'], .ipsType_richText"
            )
            if not content_elem:
                content_elem = soup.select_one("article")

            if content_elem:
                for a in content_elem.find_all("a", href=True):
                    href = a["href"]
                    if "patreon.com" in href.lower():
                        if href not in details["external_links"]:
                            details["external_links"].append(href)
                        if not is_direct_download and not patreon_redirect_url:
                            post_id = self.patreon_provider.extract_post_id(href)
                            if post_id:
                                pat_info = self.patreon_provider.check_post_access(href)
                                if pat_info.get("status") and pat_info.get("status") != "NONE":
                                    details["patreon_status"] = pat_info.get("status", "LOCKED")
                                    details["patreon_tier"] = pat_info.get("tier_str", "")
                                if pat_info.get("download_urls"):
                                    details["download_urls"].extend(pat_info["download_urls"])
                    elif any(
                        domain in href.lower()
                        for domain in [
                            "mega.nz",
                            "mediafire.com",
                            "drive.google.com",
                            "simfileshare.net",
                            "dropbox.com",
                        ]
                    ):
                        if href not in details["external_links"]:
                            details["external_links"].append(href)

                clean_body_html, body_imgs = sanitize_description_html(content_elem, self.base_url)

                # Filter gallery screenshots not already present in body
                unique_gallery = []
                for g in gallery_screenshots:
                    g_base = g.split("/")[-1].replace(".thumb.", ".")
                    if not any(g_base in b for b in body_imgs) and g not in body_imgs:
                        unique_gallery.append(g)

                gallery_html = ""
                if unique_gallery:
                    gallery_cards = "".join(
                        f'<img src="{g_url}" style="max-width: 95%; height: auto; border-radius: 8px; margin: 10px auto; display: block;" />'
                        for g_url in unique_gallery
                    )
                    gallery_html = f"""<div class="mod-gallery" style="margin-bottom: 20px; padding: 14px; background-color: #0d121f; border: 1px solid #1e293b; border-radius: 10px;"><div style="font-size: 13px; font-weight: 700; color: #60a5fa; margin-bottom: 12px; display: flex; align-items: center;">📸 Galerie &amp; Captures d'écran ({len(unique_gallery)}) :</div>{gallery_cards}</div>"""

                details["description"] = f"{gallery_html}{clean_body_html}"
                details["screenshots"] = unique_gallery if unique_gallery else gallery_screenshots
            else:
                details["screenshots"] = gallery_screenshots

            req_text, req_status, req_mods = self._extract_requirements(soup)
            details["requirements_text"] = req_text
            details["requirements_status"] = req_status
            details["requirements_mods"] = req_mods

            v_elem = soup.select_one(".cFileInfo_version, [data-role='version'], .ipsType_minorHeading")
            if v_elem:
                details["version_str"] = v_elem.get_text(strip=True)

        except Exception as e:
            logger.error(f"Error extracting details for {mod_url}: {e}", exc_info=True)

        return details

    def extract_download_candidates(self, soup: BeautifulSoup, base_url: str = "") -> List[Dict[str, Any]]:
        return _ext_dl_candidates(soup, base_url or self.base_url)

    def _extract_download_candidates(self, soup: BeautifulSoup, base_url: str = "") -> List[Dict[str, Any]]:
        return self.extract_download_candidates(soup, base_url)

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
    }

    def extract_requirements(
        self, soup: BeautifulSoup
    ) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
        """
        Extracts Requirements field from the mod info panel (.cFileInfo / .ipsDataList).
        Handles multi-requirement delimiter splitting (-, +, ,, /, &, et, and),
        resolves known LoversLab aliases, and returns individual required mod items.
        Returns (requirements_text, requirements_status, requirements_mods_list).
        """
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

        # Preserve line breaks across <br>, <p>, <div>, <li> so that multi-line requirements
        # (e.g. "WickedWhims<br/>Basemental Drugs") are not merged into single strings
        data_el_copy = copy.copy(data_el)
        for tag in data_el_copy.find_all(["br", "p", "div", "li"]):
            tag.replace_with("\n" + tag.get_text() + "\n")

        raw_text = data_el_copy.get_text(separator="\n", strip=True)
        raw_text = re.sub(r"[ \t]+", " ", raw_text)
        raw_text = re.sub(r"\n\s*\n+", "\n", raw_text).strip()

        # Exclude base game mentions ("Sims 4", "The Sims 4", "Base Game", "None", etc.)
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
                    req_mods.append({
                        "source": "loverslab",
                        "remote_id": r_id,
                        "title": t_name,
                        "url": f"https://www.loverslab.com/files/file/{r_id}-{clean_slug}/",
                    })

        for m in re.finditer(r"https?://(?:www\.)?loverslab\.com/files/file/(\d+)-?([^/\s\"'>]*)", str(data_el)):
            r_id = m.group(1)
            slug = m.group(2)
            if r_id not in seen_ids:
                seen_ids.add(r_id)
                clean_slug = urllib.parse.unquote(slug)
                t_name = clean_slug.replace("-", " ").title()
                seen_titles.add(t_name.lower())
                req_mods.append({
                    "source": "loverslab",
                    "remote_id": r_id,
                    "title": t_name,
                    "url": f"https://www.loverslab.com/files/file/{r_id}-{clean_slug}/",
                })

        text_without_urls = re.sub(r"https?://\S+", "", raw_text)
        cleaned_str = re.sub(r"\b(?:et|and|or|ou)\b", ",", text_without_urls, flags=re.IGNORECASE)
        tokens = re.split(r"[\n\r,+/&]|\s+-\s*|-\s+", cleaned_str)
        for t in tokens:
            t_clean = t.strip()
            if is_wickedwhims_name(t_clean) or is_nisa_name(t_clean):
                sub_parts = [t_clean]
            else:
                sub_parts = re.split(r"(?<=[a-zA-Z0-9])-(?=[a-zA-Z0-9])", t)

            for sp in sub_parts:
                candidate = sp.strip().strip('"\'`')
                if not candidate or len(candidate) < 2:
                    continue
                if re.fullmatch(
                    r"(?i)\s*(sims\s*4|the\s*sims\s*4|base\s*game|jeu\s*de\s*base|sims\s*4\s*base\s*game|none|aucun|aucun[e]?|n/?a|-)\s*",
                    candidate,
                ):
                    continue
                if re.search(
                    r"(?i)\b(?:dlc|expansion\s*pack|game\s*pack|stuff\s*pack|pack\s*d['’]extension|pack\s*de\s*jeu|kit\s*d['’]objets)\b",
                    candidate,
                ):
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
                    alias_info = self.KNOWN_MOD_ALIASES.get(c_lower) or self.KNOWN_MOD_ALIASES.get(c_cleaned)

                if alias_info:
                    r_id = alias_info["remote_id"]
                    if r_id not in seen_ids:
                        seen_ids.add(r_id)
                        seen_titles.add(alias_info["title"].lower())
                        req_mods.append({
                            "source": "loverslab",
                            "remote_id": r_id,
                            "title": alias_info["title"],
                            "url": alias_info["url"],
                        })
                    continue

                is_duplicate = False
                for existing in req_mods:
                    e_title = existing["title"]
                    if ModMatcher.match_score(candidate, e_title) >= 0.85:
                        is_duplicate = True
                        break
                    e_lower = e_title.lower()
                    if c_lower in e_lower or e_lower in c_lower:
                        is_duplicate = True
                        break
                    c_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", c_lower))
                    e_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", e_lower))
                    if c_words and e_words and len(c_words.intersection(e_words)) >= 1:
                        is_duplicate = True
                        break
                if is_duplicate:
                    continue

                if c_lower not in seen_titles:
                    seen_titles.add(c_lower)
                    req_mods.append({
                        "source": "loverslab",
                        "remote_id": "",
                        "title": candidate,
                        "url": "",
                    })

        if req_mods:
            if all(bool(m.get("remote_id")) for m in req_mods):
                status = "RESOLVED"
            else:
                status = "PENDING_VERIFICATION"
        else:
            status = "PENDING_VERIFICATION"

        return raw_text, status, req_mods

    _extract_requirements = extract_requirements

    def fetch_mod_by_id(self, remote_id: str) -> Optional[Dict[str, Any]]:
        session = SessionManager.get_http_session(self.provider_name)
        target_url = f"{self.base_url}/files/file/{remote_id}/"
        try:
            resp = session.get(target_url, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                title_elem = soup.select_one("h1.ipsType_pageTitle, .cFileView_title, h1")
                title = title_elem.get_text(strip=True) if title_elem else f"Mod LoversLab #{remote_id}"
                canon = soup.select_one("link[rel='canonical']")
                real_url = canon.get("href") if canon else target_url
                details = self.get_mod_details(real_url)
                return {
                    "source": "loverslab",
                    "remote_id": str(remote_id),
                    "title": title,
                    "author": "LoversLab",
                    "category": "The Sims 4",
                    "page_url": real_url,
                    "thumbnail_url": "",
                    "description": details.get("description", ""),
                    "requirements_text": details.get("requirements_text"),
                    "requirements_status": details.get("requirements_status", "NONE"),
                    "requirements_mods": details.get("requirements_mods", []),
                    "download_urls": details.get("download_urls", []),
                    "tags": ["LoversLab"],
                }
        except Exception as e:
            logger.debug(f"fetch_mod_by_id error for #{remote_id}: {e}")
        return None

    def download_mod_file(
        self,
        download_url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        return download_loverslab_file(
            download_url=download_url,
            dest_path=dest_path,
            patreon_provider=self.patreon_provider,
            base_url=self.base_url,
            progress_callback=progress_callback,
        )

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        external_links = mod_data.get("external_links", [])
        for link in external_links:
            if "patreon.com" in link.lower():
                return self.patreon_provider.check_post_access(link).get("status", "UNKNOWN")
        return "PUBLIC"
