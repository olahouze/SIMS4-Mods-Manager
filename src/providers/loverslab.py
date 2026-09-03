import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from src.providers.base import BaseSourceProvider
from src.providers.patreon import PatreonProvider
from src.core.session_manager import SessionManager
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

    def __init__(self):
        self.patreon_provider = PatreonProvider()

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
                title_elem = item.select_one(".ipsDataItem_title a, h4.ipsDataItem_title a, a[title]")
                if not title_elem or not title_elem.get("href"):
                    continue

                page_url = title_elem["href"]
                if "files/file/" not in page_url:
                    continue

                title = title_elem.get_text(strip=True)
                
                # Extract remote ID from URL: e.g. /files/file/12345-mod-name/ -> 12345
                remote_id_match = re.search(r'/files/file/(\d+)', page_url)
                remote_id = remote_id_match.group(1) if remote_id_match else page_url

                # Author
                author_elem = item.select_one(".ipsDataItem_author, a[data-ipshover]")
                author = author_elem.get_text(strip=True) if author_elem else "Inconnu"

                # Extract thumbnail with multiple fallbacks (data-src, src, inline background-image)
                thumbnail_url = ""
                thumb_elem = item.select_one("img.ipsItem_coverImage, img[data-src], img[src*='monthly_'], img[src*='uploads/'], img")
                if thumb_elem:
                    thumbnail_url = (
                        thumb_elem.get("data-src")
                        or thumb_elem.get("data-loaded-src")
                        or thumb_elem.get("src")
                        or ""
                    )

                # Check background-image in style
                if not thumbnail_url:
                    cover_elem = item.select_one("[style*='background-image'], .cFileView_cover, .ipsCoverImage")
                    if cover_elem and cover_elem.get("style"):
                        bg_match = re.search(r'url\(["\']?([^"\'\)]+)["\']?\)', cover_elem["style"])
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
                        pass

                # Badges / tags
                tags = [t.get_text(strip=True) for t in item.select(".ipsBadge, .ipsTag")]

                logger.debug(f"LoversLab item found: '{title}' (ID: {remote_id}, thumb: {bool(thumbnail_url)})")

                results.append({
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
                })

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

            # Extract remote_id
            remote_id_match = re.search(r'/files/file/(\d+)', mod_url)
            remote_id = remote_id_match.group(1) if remote_id_match else ""

            # Standard direct LoversLab download endpoint
            if remote_id:
                direct_dl_url = f"{self.base_url}/files/file/{remote_id}/?do=download"
                details["download_urls"].append({
                    "name": "Téléchargement LoversLab (Direct)",
                    "url": direct_dl_url,
                    "size": 0,
                })

            # Description content
            content_elem = soup.select_one("[data-role='commentContent'], .ipsType_richText, .cFileView_content")
            if content_elem:
                details["description"] = content_elem.get_text("\n", strip=True)

                # Find external reference & mirror links in description
                for a in content_elem.find_all("a", href=True):
                    href = a["href"]
                    if "patreon.com" in href.lower():
                        if href not in details["external_links"]:
                            details["external_links"].append(href)
                            # Analyze Patreon access and tier
                            patreon_info = self.patreon_provider.check_post_access(href)
                            if patreon_info.get("status") and patreon_info.get("status") != "NONE":
                                details["patreon_status"] = patreon_info.get("status", "UNKNOWN")
                                details["patreon_tier"] = patreon_info.get("tier_str", "")
                            if patreon_info.get("download_urls"):
                                details["download_urls"].extend(patreon_info["download_urls"])
                    elif any(domain in href.lower() for domain in ["mega.nz", "mediafire.com", "drive.google.com", "simfileshare.net", "dropbox.com"]):
                        if href not in details["external_links"]:
                            details["external_links"].append(href)

            # Check explicit download button in HTML if present
            dl_btn = soup.select_one("a[data-action='download'], a.ipsButton_important[href*='do=download']")
            if dl_btn and dl_btn.get("href"):
                dl_href = dl_btn["href"]
                if not dl_href.startswith("http"):
                    dl_href = self.base_url + dl_href
                if not any(d.get("url") == dl_href for d in details["download_urls"]):
                    details["download_urls"].insert(0, {
                        "name": "Téléchargement Direct LoversLab",
                        "url": dl_href,
                        "size": 0,
                    })

            # Version string
            version_elem = soup.select_one(".cFileView_version, [data-role='fileVersion']")
            if version_elem:
                details["version_str"] = version_elem.get_text(strip=True)

        except Exception as e:
            logger.error(f"Error getting details for {mod_url}: {e}")

        return details

    def download_mod_file(self, download_url: str, dest_path: Path) -> Tuple[bool, str]:
        """
        Downloads a direct file from LoversLab resolving multi-step IPS confirmation pages.
        """
        if "patreon.com" in download_url:
            return self.patreon_provider.download_mod_file(download_url, dest_path)

        session = SessionManager.get_http_session("loverslab")
        is_member = SessionManager.is_member_authenticated("loverslab")
        
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Lancement du téléchargement LoversLab: {download_url} (Compte membre={is_member})")
            
            resp = session.get(download_url, timeout=45, allow_redirects=True)
            logger.info(f"Réponse initiale LoversLab -> Code HTTP {resp.status_code}, Type: {resp.headers.get('Content-Type', '')}")

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
                with open(dest_path, "wb") as f:
                    f.write(resp.content)
                size_mb = dest_path.stat().st_size / (1024 * 1024)
                logger.info(f"Fichier binaire téléchargé avec succès : {dest_path.name} ({size_mb:.2f} Mo).")
                return True, str(dest_path)

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
                bin_resp = session.get(target_link, stream=True, timeout=90, allow_redirects=True)
                if bin_resp.status_code == 200:
                    with open(dest_path, "wb") as f:
                        for chunk in bin_resp.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                    size_mb = dest_path.stat().st_size / (1024 * 1024)
                    logger.info(f"Fichier final téléchargé avec succès : {dest_path.name} ({size_mb:.2f} Mo).")
                    return True, str(dest_path)
                else:
                    return False, f"Échec du téléchargement final (Code HTTP {bin_resp.status_code})"

            # Fallback: if single file attached in page
            attach_link = soup.select_one("a[href*='applications/core/interface/file/attachment.php']")
            if attach_link and attach_link.get("href"):
                att_href = attach_link["href"]
                if not att_href.startswith("http"):
                    att_href = self.base_url + att_href
                logger.info(f"Lien de pièce jointe IPS direct trouvé : {att_href}")
                bin_resp = session.get(att_href, stream=True, timeout=90, allow_redirects=True)
                if bin_resp.status_code == 200:
                    with open(dest_path, "wb") as f:
                        for chunk in bin_resp.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                    size_mb = dest_path.stat().st_size / (1024 * 1024)
                    logger.info(f"Fichier téléchargé : {dest_path.name} ({size_mb:.2f} Mo).")
                    return True, str(dest_path)

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
