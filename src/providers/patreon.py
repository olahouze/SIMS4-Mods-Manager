import re
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup

from src.providers.base import BaseSourceProvider
from src.core.session_manager import SessionManager
from src.utils.logger import logger

class PatreonProvider(BaseSourceProvider):
    """Provider for checking Patreon posts, pledge access status, and extracting download links."""

    provider_name = "patreon"
    display_name = "Patreon"
    base_url = "https://www.patreon.com"

    @classmethod
    def extract_post_id(cls, url: str) -> Optional[str]:
        """Extracts the numerical post ID from a Patreon URL."""
        # e.g. https://www.patreon.com/posts/wickedwhims-v180-102938475
        match = re.search(r'/posts/(?:[a-zA-Z0-9_-]+-)?(\d+)', url)
        if match:
            return match.group(1)
        return None

    def check_post_access(self, post_url: str) -> Dict[str, Any]:
        """
        Queries Patreon post details using the authenticated curl_cffi session.
        Returns accessibility status, download URLs, and required tier info.
        """
        post_id = self.extract_post_id(post_url)
        if not post_id:
            return {
                "status": "UNKNOWN",
                "can_view": False,
                "title": "",
                "download_urls": [],
                "external_links": [],
                "error": "Impossible d'extraire l'ID du post Patreon.",
            }

        session = SessionManager.get_http_session("patreon")
        api_url = (
            f"https://www.patreon.com/api/posts/{post_id}?"
            f"include=attachments,user,user_defined_tags,campaign.null&"
            f"fields[post]=title,content,published_at,current_user_can_view,min_cents_pledged_to_view,post_file"
        )

        try:
            resp = session.get(api_url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                post_data = data.get("data", {}).get("attributes", {})
                included = data.get("included", [])

                can_view = post_data.get("current_user_can_view", False)
                min_cents = post_data.get("min_cents_pledged_to_view", 0) or 0
                title = post_data.get("title", "")
                content_html = post_data.get("content", "")

                download_urls: List[Dict[str, Any]] = []
                external_links: List[str] = []

                # Extract direct post file
                post_file = post_data.get("post_file")
                if post_file and isinstance(post_file, dict):
                    if post_file.get("url"):
                        download_urls.append({
                            "name": post_file.get("name", "Patreon File"),
                            "url": post_file.get("url"),
                            "size": post_file.get("size", 0),
                        })

                # Extract attachments from included
                for item in included:
                    if item.get("type") == "attachment":
                        attr = item.get("attributes", {})
                        if attr.get("url"):
                            download_urls.append({
                                "name": attr.get("name", "Attachment"),
                                "url": attr.get("url"),
                                "size": attr.get("size", 0),
                            })

                # Extract external links from post HTML content
                if content_html:
                    soup = BeautifulSoup(content_html, "html.parser")
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if any(host in href.lower() for host in ["mega.nz", "mediafire.com", "drive.google.com", "simfileshare.net", "dropbox.com"]):
                            external_links.append(href)

                if can_view:
                    status = "PUBLIC" if min_cents == 0 else "UNLOCKED"
                else:
                    status = "LOCKED"

                tier_str = f"${min_cents / 100:.2f}/mois" if min_cents > 0 else ""

                return {
                    "status": status,
                    "can_view": can_view,
                    "title": title,
                    "min_cents": min_cents,
                    "tier_str": tier_str,
                    "download_urls": download_urls,
                    "external_links": external_links,
                    "published_at": post_data.get("published_at"),
                }
            elif resp.status_code in [401, 403]:
                return {
                    "status": "LOCKED",
                    "can_view": False,
                    "title": "",
                    "download_urls": [],
                    "external_links": [],
                    "tier_str": "Accès Patreon Requis",
                }
        except Exception as e:
            logger.error(f"Error checking Patreon post {post_url}: {e}")

        # Fallback: check via direct HTML page scraping
        try:
            page_resp = session.get(post_url, timeout=15)
            if page_resp.status_code == 200:
                html = page_resp.text
                if "locked" in html.lower() or "unlock this post" in html.lower():
                    return {"status": "LOCKED", "can_view": False, "download_urls": [], "external_links": []}
                else:
                    return {"status": "PUBLIC", "can_view": True, "download_urls": [], "external_links": []}
        except Exception as e:
            logger.error(f"Fallback page check failed: {e}")

        return {"status": "UNKNOWN", "can_view": False, "download_urls": [], "external_links": []}

    def scrape_catalog(self, page: int = 1, limit: int = 25) -> List[Dict[str, Any]]:
        # Patreon does not have a global public category catalog like LoversLab,
        # it is resolved via links extracted from LoversLab or user campaigns.
        return []

    def get_mod_details(self, mod_url: str) -> Dict[str, Any]:
        return self.check_post_access(mod_url)

    def download_mod_file(self, download_url: str, dest_path: Path) -> Tuple[bool, str]:
        session = SessionManager.get_http_session("patreon")
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            resp = session.get(download_url, stream=True, timeout=60)
            if resp.status_code == 200:
                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                return True, str(dest_path)
            else:
                return False, f"Erreur HTTP {resp.status_code} lors du téléchargement."
        except Exception as e:
            return False, f"Exception lors du téléchargement: {e}"

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        page_url = mod_data.get("page_url", "")
        res = self.check_post_access(page_url)
        return res.get("status", "UNKNOWN")
