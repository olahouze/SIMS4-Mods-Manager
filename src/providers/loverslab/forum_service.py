"""
LoversLabForumService: Verification of previous comments and submission of comments
on LoversLab mod topics.
"""

import re
from typing import List, Tuple, Optional
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from src.core.session_manager import SessionManager
from src.utils.logger import logger


class LoversLabForumService:
    """Service handling interactions with the LoversLab forum/comments system."""

    @staticmethod
    def check_user_already_commented(page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Scrapes the live LoversLab file or topic page to check if the authenticated user
        has already posted a comment referencing the missing requirements.
        Returns (already_commented: bool, formatted_datetime: Optional[str]).
        """
        if not page_url:
            return False, None

        acc = SessionManager.get_saved_session("loverslab")
        if not acc or not SessionManager.is_member_authenticated("loverslab"):
            return False, None

        cookies = acc.get_cookies_dict()
        member_id = str(cookies.get("ips4_member_id") or "").strip()
        user_display = (acc.user_display_name or "").strip().lower()

        session = SessionManager.get_http_session("loverslab")
        try:
            resp = session.get(page_url, timeout=15)
            if resp.status_code != 200:
                logger.debug(f"check_user_already_commented: HTTP {resp.status_code} on {page_url}")
                return False, None

            soup = BeautifulSoup(resp.text, "html.parser")

            def _search_comments_in_soup(page_soup: BeautifulSoup) -> Tuple[bool, Optional[str]]:
                comment_nodes = page_soup.select(
                    "article.ipsComment, article.cPost, div[id^='comment-'], div[id^='elComment_']"
                )
                for node in comment_nodes:
                    node_author_id = str(node.get("data-memberid") or node.get("data-member-id") or "").strip()
                    author_link = node.select_one("a[href*='/profile/']")
                    author_href = author_link.get("href", "") if author_link else ""
                    author_text = author_link.get_text(strip=True).lower() if author_link else ""

                    is_user = False
                    if member_id and member_id != "0":
                        if node_author_id == member_id or f"/profile/{member_id}-" in author_href:
                            is_user = True
                    if not is_user and user_display and user_display in author_text:
                        is_user = True

                    if not is_user:
                        continue

                    content_node = (
                        node.select_one("[data-role='commentContent']") or node.select_one(".ipsType_richText") or node
                    )
                    content_text = content_node.get_text(separator=" ", strip=True).lower()

                    has_signature = (
                        "requirement" in content_text or "not identified" in content_text or "not found" in content_text
                    )
                    if not has_signature:
                        continue

                    if required_keywords:
                        kw_matched = any(kw.lower().strip() in content_text for kw in required_keywords if kw)
                        if not kw_matched:
                            continue

                    time_node = node.select_one("time")
                    date_str = ""
                    if time_node:
                        raw_date = time_node.get("title") or time_node.get("datetime") or time_node.get_text(strip=True)
                        try:
                            dt = date_parser.parse(raw_date, dayfirst=True)
                            date_str = dt.strftime("%d/%m/%Y à %H:%M")
                        except Exception:
                            date_str = raw_date
                    return True, date_str or "Récemment"

                return False, None

            found, date_str = _search_comments_in_soup(soup)
            if found:
                return True, date_str

            # Linked discussion topic
            topic_link = soup.select_one("a[href*='/topic/']")
            if topic_link and topic_link.get("href"):
                topic_url = topic_link["href"].split("?")[0]
                try:
                    topic_resp = session.get(topic_url, timeout=12)
                    if topic_resp.status_code == 200:
                        topic_soup = BeautifulSoup(topic_resp.text, "html.parser")
                        found, date_str = _search_comments_in_soup(topic_soup)
                        if found:
                            return True, date_str
                except Exception as ex_topic:
                    logger.debug(f"Linked topic check failed for {topic_url}: {ex_topic}")

            return False, None

        except Exception as e:
            logger.debug(f"check_user_already_commented exception for {page_url}: {e}")
            return False, None

    @staticmethod
    def post_mod_comment(page_url: str, message: str) -> Tuple[bool, str]:
        """
        Posts a comment or message on the LoversLab file page using authenticated IPS session and CSRF key.
        """
        if not page_url:
            return False, "URL du mod invalide ou manquante."

        if not SessionManager.is_member_authenticated("loverslab"):
            return False, "Utilisateur non authentifié avec un compte membre LoversLab."

        session = SessionManager.get_http_session("loverslab")
        try:
            get_resp = session.get(page_url, timeout=15)
            if get_resp.status_code != 200:
                return False, f"Impossible de charger la page du mod (Erreur HTTP {get_resp.status_code})."

            soup = BeautifulSoup(get_resp.text, "html.parser")

            csrf_input = soup.find("input", {"name": "csrfKey"})
            csrf_key = csrf_input["value"] if csrf_input and csrf_input.get("value") else None
            if not csrf_key:
                match = re.search(r'csrfKey["\']?\s*[:=]\s*["\']([a-f0-9]{32,})["\']', get_resp.text)
                if match:
                    csrf_key = match.group(1)

            if not csrf_key:
                return False, "Jeton de sécurité CSRF introuvable sur la page LoversLab."

            form_action = page_url.rstrip("/") + "/?do=addComment"
            for form in soup.find_all("form"):
                action = form.get("action", "")
                if "do=addComment" in action or "do=reply" in action:
                    form_action = action
                    break

            post_data = {
                "csrfKey": csrf_key,
                "comment_value": message,
                "file_comment_value": message,
                "comment_value_editor": message,
                "topic_comment": message,
            }

            headers = {
                "Referer": page_url,
                "Origin": "https://www.loverslab.com",
            }

            post_resp = session.post(form_action, data=post_data, headers=headers, timeout=20)
            if post_resp.status_code in [200, 302, 303]:
                if post_resp.status_code == 200:
                    post_soup = BeautifulSoup(post_resp.text, "html.parser")
                    err_box = post_soup.select_one(".ipsMessage_error, .ipsType_warning")
                    if err_box:
                        err_text = err_box.get_text(strip=True)
                        return False, f"Erreur LoversLab: {err_text}"

                logger.info(f"Commentaire publié avec succès sur LoversLab ({page_url}).")
                return True, "Message publié avec succès sur le forum LoversLab."
            if post_resp.status_code == 403:
                return False, "Accès refusé par LoversLab (Erreur 403 / Protection Cloudflare)."
            return False, f"Erreur HTTP {post_resp.status_code} lors de la publication du message."

        except Exception as e:
            logger.error(f"Erreur lors de la publication du commentaire sur {page_url}: {e}")
            return False, f"Exception lors de la publication: {e}"
