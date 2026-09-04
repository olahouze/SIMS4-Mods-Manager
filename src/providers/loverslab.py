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
from src.core.session_manager import SessionManager
from src.utils.logger import logger
from src.utils.network import stream_download, is_external_hosted


class LoversLabProvider(BaseSourceProvider):
    """
    Provider for scraping LoversLab The Sims 4 files category (161),
    extracting attachments, adult content handling, and identifying external/Patreon links.
    """

    provider_name = "loverslab"
    display_name = "LoversLab"
    base_url = "https://www.loverslab.com"
    category_url = "https://www.loverslab.com/files/category/161-the-sims-4/"

    def __init__(self):
        self.patreon_provider = PatreonProvider()

    def get_total_pages(self) -> int:
        """Extracts the total number of pages available in category 161 on LoversLab."""
        session = SessionManager.get_http_session(self.provider_name)
        try:
            resp = session.get(self.category_url, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                pag = soup.select_one("[data-pages]")
                if pag and pag.get("data-pages"):
                    return int(pag["data-pages"])
                pages = []
                for a in soup.select("ul.ipsPagination a[href*='/page/']"):
                    m = re.search(r"/page/(\d+)", a.get("href", ""))
                    if m:
                        pages.append(int(m.group(1)))
                if pages:
                    return max(pages)
        except Exception as e:
            logger.debug(f"Impossible d'extraire le nombre total de pages LoversLab: {e}")
        return 1

    def scrape_catalog(self, page: int = 1, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Scrapes a specific page of category 161 on LoversLab.
        """
        url = self.category_url if page == 1 else f"{self.category_url}page/{page}/"
        session = SessionManager.get_http_session("loverslab")

        logger.info(f"Scraping LoversLab catalog page {page}: {url}")
        results: List[Dict[str, Any]] = []

        try:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"LoversLab request returned status {resp.status_code}")
                return results

            soup = BeautifulSoup(resp.text, "html.parser")
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

                # Extract remote ID from URL: e.g. /files/file/12345-mod-name/ -> 12345
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

                # Author
                author_elem = item.select_one(".ipsDataItem_author, a[data-ipshover]")
                author = author_elem.get_text(strip=True) if author_elem else "Inconnu"
                author = author.replace("\u200b", "").replace("\ufeff", "").strip()

                # Extract thumbnail with multiple fallbacks (data-src, src, inline background-image)
                thumbnail_url = ""
                thumb_elem = item.select_one(
                    "img.ipsItem_coverImage, img[data-src], img[src*='monthly_'], img[src*='uploads/'], img"
                )
                if thumb_elem:
                    thumbnail_url = (
                        thumb_elem.get("data-src") or thumb_elem.get("data-loaded-src") or thumb_elem.get("src") or ""
                    )

                # Check background-image in style
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

                # Updated or published date
                time_elem = item.select_one("time[datetime]")
                updated_date = None
                if time_elem and time_elem.get("datetime"):
                    try:
                        updated_date = date_parser.parse(time_elem["datetime"]).replace(tzinfo=None)
                    except Exception:
                        logger.debug(f"Could not parse date for item {remote_id}: {time_elem.get('datetime')}")

                # Badges / tags
                tags = [t.get_text(strip=True) for t in item.select(".ipsBadge, .ipsTag") if t.get_text(strip=True)]

                logger.debug(f"LoversLab item found: '{title}' (ID: {remote_id}, thumb: {bool(thumbnail_url)})")

                results.append(
                    {
                        "source": self.provider_name,
                        "remote_id": remote_id,
                        "title": title,
                        "author": author,
                        "category": "The Sims 4",
                        "tags": tags,
                        "page_url": page_url,
                        "thumbnail_url": thumbnail_url,
                        "updated_date": updated_date,
                        "published_date": updated_date,
                        "patreon_status": "NONE",
                        "patreon_tier": "",
                    }
                )

            # Parallel rapid check of download target (Patreon redirect vs direct LoversLab)
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

                with ThreadPoolExecutor(max_workers=5) as pool:
                    results = list(pool.map(_inspect_item_target, results))

            logger.info(f"LoversLab page {page} scraping finished: {len(results)} mods trouvés.")

        except Exception as e:
            logger.error(f"Error while scraping LoversLab page {page}: {e}", exc_info=True)

        return results

    def get_mod_details(self, mod_url: str) -> Dict[str, Any]:
        """
        Loads the detail page of a mod on LoversLab, extracting description,
        direct download links, and identifying external links (Patreon, Mega, Drive, etc.).
        """
        session = SessionManager.get_http_session("loverslab")
        details: Dict[str, Any] = {
            "description": "",
            "download_urls": [],
            "external_links": [],
            "patreon_status": "NONE",
            "patreon_tier": "",
            "version_str": "",
        }

        try:
            resp = session.get(mod_url, timeout=20)
            if resp.status_code != 200:
                return details

            soup = BeautifulSoup(resp.text, "html.parser")

            # Standard direct LoversLab download endpoint & redirect detection
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

            # Description & Screenshot Gallery extraction
            art_elem = soup.select_one("article")
            gallery_screenshots: List[str] = []
            carousel_candidates = []
            if art_elem:
                prev_car = art_elem.find_previous(class_="ipsCarousel")
                if prev_car:
                    carousel_candidates.append(prev_car)
            if not carousel_candidates:
                for car in soup.select(".cFileTop .ipsCarousel, .cFileView_screenshots"):
                    if car not in carousel_candidates:
                        carousel_candidates.append(car)

            for car in carousel_candidates:
                for it in car.select("[data-fullurl], li, .ipsThumb"):
                    u = it.get("data-fullurl")
                    if not u:
                        f_el = it.select_one("[data-fullurl]")
                        if f_el:
                            u = f_el.get("data-fullurl")
                    if not u:
                        img_el = it.select_one("img")
                        if img_el:
                            u = img_el.get("data-src") or img_el.get("src")
                    if not u:
                        bg = it.get("style", "")
                        m_bg = re.search(r'url\(\s*["\']?(.*?)["\']?\s*\)', bg)
                        if m_bg:
                            u = m_bg.group(1)
                    if u:
                        if u.startswith("/"):
                            u = f"{self.base_url}{u}"
                        if u.startswith("http") and not any(
                            j in u.lower() for j in ["/themes/", "/reactions/", "icon_", "avatar", "logo", ".svg"]
                        ):
                            if u not in gallery_screenshots:
                                gallery_screenshots.append(u)

            # Target rich text container
            content_elem = soup.select_one(
                "article div.ipsType_richText, .cFileView_content div.ipsType_richText, [data-role='commentContent'], .ipsType_richText"
            )
            if not content_elem:
                content_elem = art_elem

            if content_elem:
                # 1. Extract links for Patreon/mirrors before cleaning
                for a in content_elem.find_all("a", href=True):
                    href = a["href"]
                    if "patreon.com" in href.lower():
                        if href not in details["external_links"]:
                            details["external_links"].append(href)
                        # Only if NOT already confirmed as direct LoversLab download and no patreon redirect
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

                # 2. Clean element to produce structured HTML without changelog junk
                clean_elem = copy.deepcopy(content_elem)

                # Remove changelog blocks, menus, scripts, styles, forms, headers, and timestamps
                for junk in clean_elem.select(
                    ".cFileChangelog, [data-role='changelog'], div#changeLogData, .ipsMenu, script, style, iframe, form, button, input, noscript, h2, hr, p.ipsType_light"
                ):
                    junk.decompose()

                # Unwrap spoilers so images inside are visible
                for sp in clean_elem.select(".ipsSpoiler"):
                    sp_content = sp.select_one(".ipsSpoiler_contents")
                    if sp_content:
                        sp.replace_with(sp_content)

                # Convert standalone image links <a href="...png"> to <img> if no img inside
                for a in clean_elem.select("a[href]"):
                    href = a.get("href", "")
                    if any(
                        ext in href.lower()
                        for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", "uploads/monthly"]
                    ) and not a.find("img"):
                        new_img = soup.new_tag("img", src=href)
                        a.replace_with(new_img)

                # Clean author inline styles to avoid dark-mode color clashes (e.g. background-color:#0d0d0d; color:#999999;)
                for tag in clean_elem.find_all(True):
                    st = tag.get("style", "")
                    if st:
                        new_st = re.sub(r"background(?:-color)?\s*:\s*[^;]+;?", "", st, flags=re.IGNORECASE)
                        new_st = re.sub(r"color\s*:\s*[^;]+;?", "", new_st, flags=re.IGNORECASE)
                        new_st = new_st.strip()
                        if new_st:
                            tag["style"] = new_st
                        else:
                            del tag["style"]

                # Process images for proper URLs and responsive rendering
                body_imgs: List[str] = []
                for img in clean_elem.select("img"):
                    src = img.get("data-src") or img.get("src")
                    if src:
                        if src.startswith("/"):
                            src = f"{self.base_url}{src}"
                        img["src"] = src
                        body_imgs.append(src)
                    # Clean clutter attributes
                    for attr in ["data-ratio", "data-fileid", "srcset", "sizes", "class", "loading"]:
                        if attr in img.attrs:
                            del img.attrs[attr]
                    img["style"] = (
                        "max-width: 95%; height: auto; border-radius: 8px; margin: 10px auto; display: block;"
                    )

                # Process links for absolute URLs
                for a in clean_elem.select("a"):
                    href = a.get("href", "")
                    if href.startswith("/"):
                        a["href"] = f"{self.base_url}{href}"
                    a["style"] = "color: #60a5fa; text-decoration: underline;"

                clean_body_html = str(clean_elem)

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

            # Check explicit download button in HTML if present
            dl_btn = soup.select_one("a[data-action='download'], a.ipsButton_important[href*='do=download']")
            if dl_btn and dl_btn.get("href") and not patreon_redirect_url:
                dl_href = dl_btn["href"]
                if not dl_href.startswith("http"):
                    dl_href = self.base_url + dl_href
                if not any(d.get("url") == dl_href for d in details["download_urls"]):
                    details["download_urls"].insert(
                        0,
                        {
                            "name": "Téléchargement Direct LoversLab",
                            "url": dl_href,
                            "size": 0,
                        },
                    )

            # Version string
            version_elem = soup.select_one(".cFileView_version, [data-role='fileVersion']")
            if version_elem:
                details["version_str"] = version_elem.get_text(strip=True)

        except Exception as e:
            logger.error(f"Error getting details for {mod_url}: {e}")

        return details

    def download_mod_file(
        self,
        download_url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        """
        Downloads a direct file from LoversLab resolving multi-step IPS confirmation pages.
        """
        if "patreon.com" in download_url:
            return self.patreon_provider.download_mod_file(download_url, dest_path, progress_callback=progress_callback)

        session = SessionManager.get_http_session("loverslab")
        is_member = SessionManager.is_member_authenticated("loverslab")

        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Lancement du téléchargement LoversLab: {download_url} (Compte membre={is_member})")
            if progress_callback:
                progress_callback(
                    5, "Connexion aux serveurs LoversLab...", "Résolution de la page de téléchargement..."
                )

            resp = session.get(download_url, timeout=45, allow_redirects=False)
            logger.info(
                f"Réponse initiale LoversLab -> Code HTTP {resp.status_code}, Type: {resp.headers.get('Content-Type', '')}"
            )

            # Check for redirect to Patreon or external site
            if resp.status_code in [301, 302, 303, 307, 308]:
                target = resp.headers.get("Location", "")
                logger.info(f"Redirection détectée lors du téléchargement: {target}")
                if "patreon.com" in target.lower():
                    return self.patreon_provider.download_mod_file(
                        target, dest_path, progress_callback=progress_callback
                    )

                matched_host = is_external_hosted(target)
                if matched_host:
                    msg = f"Ce contenu est hébergé sur un service externe ({matched_host}). Veuillez l'ouvrir dans votre navigateur pour le télécharger."
                    logger.warning(msg)
                    return False, msg

                # Otherwise follow redirect
                resp = session.get(target, timeout=45, allow_redirects=True)

            logger.info(
                f"Réponse LoversLab -> Code HTTP {resp.status_code}, Type: {resp.headers.get('Content-Type', '')}"
            )

            final_url = str(getattr(resp, "url", ""))
            matched_host = is_external_hosted(final_url)
            if matched_host:
                msg = f"Ce contenu est hébergé sur un service externe ({matched_host}). Veuillez l'ouvrir dans votre navigateur pour le télécharger."
                logger.warning(msg)
                return False, msg

            if resp.status_code == 403:
                msg = "Accès refusé par LoversLab (Code 403). Le téléchargement exige un compte membre connecté. Veuillez vous connecter dans l'onglet 'Comptes & Anti-Bot'."
                logger.error(msg)
                return False, msg
            elif resp.status_code in [504, 502]:
                msg = f"Délai d'attente dépassé sur le serveur LoversLab (Code {resp.status_code}). Veuillez réessayer dans quelques instants."
                logger.error(msg)
                return False, msg
            elif resp.status_code != 200:
                return False, f"Code d'erreur HTTP {resp.status_code}"

            content_type = resp.headers.get("Content-Type", "").lower()
            content_disp = resp.headers.get("Content-Disposition", "").lower()

            # Case A: Directly received binary stream
            if "html" not in content_type or "attachment" in content_disp or "filename=" in content_disp:
                return stream_download(resp, dest_path, progress_callback, "Téléchargement Direct")

            # Case B: Invision Community confirmation or multi-file selection page
            soup = BeautifulSoup(resp.text, "html.parser")

            # Check for login requirement inside HTML
            if "data-focus-guest" in resp.text and ("Sign In" in resp.text or "Existing user" in resp.text):
                msg = "LoversLab exige d'être connecté avec un compte membre pour télécharger. Veuillez vous connecter dans l'onglet 'Comptes & Anti-Bot'."
                logger.error(msg)
                return False, msg

            # Search confirmation link
            target_link = None
            candidates = soup.select(
                "a[href*='do=download'][href*='confirm='], a[href*='do=download&r='], a.ipsButton_primary[href*='do=download'], a[data-action='download']"
            )
            for cand in candidates:
                cand_href = cand.get("href", "")
                if cand_href and not cand_href.startswith("#"):
                    if not cand_href.startswith("http"):
                        cand_href = self.base_url + cand_href
                    target_link = cand_href
                    break

            if target_link:
                logger.info(f"Lien de confirmation IPS résolu : {target_link}. Lancement du flux binaire...")
                if progress_callback:
                    progress_callback(10, "Lien direct résolu", "Démarrage du téléchargement...")
                bin_resp = session.get(target_link, stream=True, timeout=90, allow_redirects=True)
                if bin_resp.status_code == 200:
                    return stream_download(bin_resp, dest_path, progress_callback, "Téléchargement LoversLab")
                else:
                    return False, f"Échec du téléchargement final (Code HTTP {bin_resp.status_code})"

            # Fallback: if single file attached in page
            attach_link = soup.select_one("a[href*='applications/core/interface/file/attachment.php']")
            if attach_link and attach_link.get("href"):
                att_href = attach_link["href"]
                if not att_href.startswith("http"):
                    att_href = self.base_url + att_href
                logger.info(f"Lien de pièce jointe IPS direct trouvé : {att_href}")
                if progress_callback:
                    progress_callback(10, "Pièce jointe trouvée", "Démarrage du téléchargement...")
                bin_resp = session.get(att_href, stream=True, timeout=90, allow_redirects=True)
                if bin_resp.status_code == 200:
                    return stream_download(bin_resp, dest_path, progress_callback, "Téléchargement LoversLab")
                else:
                    return False, f"Échec du téléchargement final (Code HTTP {bin_resp.status_code})"

            return False, "Impossible de résoudre le bouton de téléchargement final sur la page LoversLab."

        except Exception as e:
            logger.error(f"Exception lors du téléchargement LoversLab ({download_url}): {e}", exc_info=True)
            return False, str(e)

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        external_links = mod_data.get("external_links", [])
        for link in external_links:
            if "patreon.com" in link.lower():
                return self.patreon_provider.check_post_access(link).get("status", "UNKNOWN")
        return "PUBLIC"
