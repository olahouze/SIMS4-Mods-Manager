from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Callable
from bs4 import BeautifulSoup

from src.providers.base import BaseSourceProvider
from src.providers.patreon import PatreonProvider
from src.providers.loverslab.downloader import download_loverslab_file, extract_download_candidates as _ext_dl_candidates
from src.providers.loverslab.parsers import extract_gallery_screenshots, sanitize_description_html
from src.providers.loverslab.requirements_extractor import (
    extract_loverslab_requirements,
    KNOWN_MOD_ALIASES,
)
from src.providers.loverslab.forum_service import LoversLabForumService
from src.providers.loverslab.page_parser import parse_category_page_html
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.utils.logger import logger


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
        {"id": "174", "name": "WickedWhims", "slug": "174-wickedwhims", "url": "https://www.loverslab.com/files/category/174-wickedwhims/", "default_pages": 16},
        {"id": "201", "name": "Animations - WickedWhims", "slug": "201-animations-wickedwhims", "url": "https://www.loverslab.com/files/category/201-animations-wickedwhims/", "default_pages": 7},
        {"id": "215", "name": "Translations - WickedWhims", "slug": "215-translations-wickedwhims", "url": "https://www.loverslab.com/files/category/215-translations-wickedwhims/", "default_pages": 5},
        {"id": "202", "name": "Animations - Other", "slug": "202-animations-other", "url": "https://www.loverslab.com/files/category/202-animations-other/", "default_pages": 7},
        {"id": "200", "name": "Extensions", "slug": "200-extensions", "url": "https://www.loverslab.com/files/category/200-extensions/", "default_pages": 3},
        {"id": "203", "name": "Clothing", "slug": "203-clothing", "url": "https://www.loverslab.com/files/category/203-clothing/", "default_pages": 128},
        {"id": "204", "name": "Accessories & Makeup", "slug": "204-accessories-makeup", "url": "https://www.loverslab.com/files/category/204-accessories-makeup/", "default_pages": 16},
        {"id": "205", "name": "Body Parts", "slug": "205-body-parts", "url": "https://www.loverslab.com/files/category/205-body-parts/", "default_pages": 12},
        {"id": "206", "name": "Objects", "slug": "206-objects", "url": "https://www.loverslab.com/files/category/206-objects/", "default_pages": 86},
        {"id": "404", "name": "Paintings & Posters", "slug": "404-paintings-posters", "url": "https://www.loverslab.com/files/category/404-paintings-posters/", "default_pages": 14},
        {"id": "207", "name": "Lots", "slug": "207-lots", "url": "https://www.loverslab.com/files/category/207-lots/", "default_pages": 18},
        {"id": "209", "name": "Translations", "slug": "209-translations", "url": "https://www.loverslab.com/files/category/209-translations/", "default_pages": 35},
        {"id": "210", "name": "Other", "slug": "210-other", "url": "https://www.loverslab.com/files/category/210-other/", "default_pages": 23},
        {"id": "216", "name": "Uncategorized", "slug": "216-uncategorized", "url": "https://www.loverslab.com/files/category/216-uncategorized/", "default_pages": 27},
    ]

    KNOWN_MOD_ALIASES: Dict[str, Dict[str, str]] = KNOWN_MOD_ALIASES

    def __init__(self):
        super().__init__()
        self.patreon_provider = PatreonProvider()
        self._category_pages_cache: Dict[str, int] = {c["id"]: c["default_pages"] for c in self.CATEGORIES}
        self.current_category_info: str = "WickedWhims"

    def update_category_detected_pages(self, cat_id: str, detected_pages: int) -> None:
        if detected_pages > 0:
            self._category_pages_cache[cat_id] = detected_pages

    def _get_category_page_counts(self) -> List[Tuple[Dict[str, Any], int]]:
        return [(cat, self._category_pages_cache.get(cat["id"], cat["default_pages"])) for cat in self.CATEGORIES]

    def get_total_pages(self) -> int:
        return sum(pages for _, pages in self._get_category_page_counts())

    def _resolve_category_page(self, global_page: int) -> Tuple[Dict[str, Any], int, int]:
        counts = self._get_category_page_counts()
        remaining = max(1, global_page)
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
            results, detected_pages = parse_category_page_html(soup, category, self.base_url, page)

            if detected_pages and page == 1:
                self.update_category_detected_pages(category["id"], detected_pages)

            if results:
                def _inspect_item_target(entry: Dict[str, Any]) -> Dict[str, Any]:
                    p_url = entry["page_url"]
                    dl_chk = p_url.rstrip("/") + "/?do=download"
                    try:
                        r_chk = session.get(dl_chk, allow_redirects=False, timeout=6)
                        loc = r_chk.headers.get("Location", "")
                        if r_chk.status_code in [301, 302, 303, 307, 308]:
                            if "patreon.com" in loc.lower():
                                pat_info = self.patreon_provider.check_post_access(loc)
                                entry["patreon_status"] = pat_info.get("status", "PUBLIC")
                                entry["patreon_tier"] = pat_info.get("tier_str", "")
                                if "Patreon" not in entry["tags"]:
                                    entry["tags"].append("Patreon")
                            elif loc and "loverslab.com" not in loc.lower():
                                entry["patreon_status"] = "NONE"
                                ext_list = entry.setdefault("external_links", [])
                                if loc not in ext_list:
                                    ext_list.append(loc)
                            else:
                                entry["patreon_status"] = "NONE"
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
                try:
                    r_chk = session.head(direct_dl_url, allow_redirects=False, timeout=3.0)
                except Exception:
                    r_chk = None

                if r_chk is None or not isinstance(getattr(r_chk, "status_code", None), int) or r_chk.status_code == 405:
                    r_chk = session.get(direct_dl_url, allow_redirects=False, timeout=3.0)

                if r_chk.status_code in [301, 302, 303, 307, 308]:
                    loc = r_chk.headers.get("Location", "")
                    if "patreon.com" in loc.lower():
                        patreon_redirect_url = loc
                    elif loc and loc not in details["external_links"]:
                        details["external_links"].append(loc)
                elif r_chk.status_code in [200, 403]:
                    is_direct_download = True
                    details["download_urls"].append({
                        "name": "Téléchargement LoversLab (Direct)",
                        "url": direct_dl_url,
                        "size": 0,
                    })
            except Exception as e:
                logger.debug(f"Redirect check error for {direct_dl_url}: {e}")

            if patreon_redirect_url:
                if patreon_redirect_url not in details["external_links"]:
                    details["external_links"].append(patreon_redirect_url)
                pat_info = self.patreon_provider.check_post_access(patreon_redirect_url)
                can_view = pat_info.get("can_view", False)
                p_status = pat_info.get("status", "UNKNOWN")
                tier_str = pat_info.get("tier_str", "")
                is_patreon_member = SessionManager.is_member_authenticated("patreon")

                if p_status == "LOCKED" or (not can_view and not is_patreon_member):
                    details["source"] = "patreon"
                    details["patreon_status"] = "LOCKED"
                    details["patreon_tier"] = tier_str or "Abonnement requis"
                    details["download_urls"] = []
                    if "Patreon" not in details["tags"]:
                        details["tags"].append("Patreon")
                else:
                    details["patreon_status"] = "PUBLIC"
                    dl_urls = pat_info.get("download_urls", [])
                    if dl_urls:
                        details["download_urls"].extend(dl_urls)
                    else:
                        details["download_urls"].append({
                            "name": "Post Patreon (Téléchargement)",
                            "url": patreon_redirect_url,
                            "size": 0,
                        })

            gallery_screenshots: List[str] = extract_gallery_screenshots(soup, self.base_url)
            content_elem = soup.select_one(
                "article div.ipsType_richText, .cFileView_content div.ipsType_richText, [data-role='commentContent'], .ipsType_richText"
            ) or soup.select_one("article")

            if content_elem:
                for a in content_elem.find_all("a", href=True):
                    href = a["href"]
                    if "patreon.com" in href.lower():
                        if href not in details["external_links"]:
                            details["external_links"].append(href)
                        if not is_direct_download and not patreon_redirect_url and not details["download_urls"]:
                            post_id = self.patreon_provider.extract_post_id(href)
                            if post_id:
                                pat_info = self.patreon_provider.check_post_access(href)
                                if pat_info.get("status") and pat_info.get("status") != "NONE":
                                    details["patreon_status"] = pat_info.get("status", "LOCKED")
                                    details["patreon_tier"] = pat_info.get("tier_str", "")
                                if pat_info.get("download_urls"):
                                    details["download_urls"].extend(pat_info["download_urls"])
                    elif any(d in href.lower() for d in ["mega.nz", "mediafire.com", "drive.google.com", "simfileshare.net", "dropbox.com"]):
                        if href not in details["external_links"]:
                            details["external_links"].append(href)

                clean_body_html, body_imgs = sanitize_description_html(content_elem, self.base_url)
                unique_gallery = [
                    g for g in gallery_screenshots
                    if not any(g.split("/")[-1].replace(".thumb.", ".") in b for b in body_imgs) and g not in body_imgs
                ]

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

            req_text, req_status, req_mods = self.extract_requirements(soup)
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

    def extract_requirements(
        self, soup: BeautifulSoup
    ) -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
        return extract_loverslab_requirements(soup, self.KNOWN_MOD_ALIASES)

    _extract_requirements = extract_requirements

    def fetch_mod_by_id(self, remote_id: str) -> Optional[Dict[str, Any]]:
        session = SessionManager.get_http_session(self.provider_name)
        target_url = f"{self.base_url}/files/file/{remote_id}/"
        try:
            resp = session.get(target_url, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                title_elem = soup.select_one("h1.ipsType_pageTitle, .cFileView_title, h1")
                author_elem = soup.select_one(".ipsDataItem_author, a[data-ipshover]")
                v_elem = soup.select_one(".cFileInfo_version, [data-role='version']")
                return {
                    "source": self.provider_name,
                    "remote_id": str(remote_id),
                    "title": title_elem.get_text(strip=True) if title_elem else f"Mod #{remote_id}",
                    "author": author_elem.get_text(strip=True) if author_elem else "Inconnu",
                    "page_url": target_url,
                    "version_str": v_elem.get_text(strip=True) if v_elem else "",
                }
        except Exception as e:
            logger.debug(f"fetch_mod_by_id failed for {remote_id}: {e}")
        return None

    def download_mod_file(
        self,
        download_url: Optional[str] = None,
        dest_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
        **kwargs,
    ) -> Tuple[bool, str]:
        target_url = download_url or kwargs.get("mod_url", "")
        target_path = dest_path or kwargs.get("dest_folder") or kwargs.get("dest_path")
        return download_loverslab_file(
            download_url=target_url,
            dest_path=target_path,
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

    def check_user_already_commented(
        self, page_url: str, required_keywords: List[str]
    ) -> Tuple[bool, Optional[str]]:
        return LoversLabForumService.check_user_already_commented(page_url, required_keywords)

    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        return LoversLabForumService.post_mod_comment(page_url, message)
