"""
PageParser: Pure HTML parsing functions for LoversLab category listings and file pages.
"""

import re
import urllib.parse
from typing import Dict, List, Any, Tuple, Optional
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from src.utils.logger import logger


def parse_category_page_html(
    soup: BeautifulSoup,
    category: Dict[str, Any],
    base_url: str = "https://www.loverslab.com",
    page: int = 1,
) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """
    Parses a LoversLab category page HTML to extract mod cards and total page count.
    """
    detected_pages: Optional[int] = None
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

    items = soup.select("li.ipsDataItem, li[data-rowid]")
    results: List[Dict[str, Any]] = []

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
                thumbnail_url = base_url + thumbnail_url

        time_elem = item.select_one("time[datetime]")
        updated_date = None
        if time_elem and time_elem.get("datetime"):
            try:
                updated_date = date_parser.parse(time_elem["datetime"]).replace(tzinfo=None)
            except Exception:
                logger.debug(f"Could not parse date for item {remote_id}: {time_elem.get('datetime')}")

        tags = [t.get_text(strip=True) for t in item.select(".ipsBadge, .ipsTag") if t.get_text(strip=True)]
        if category.get("name") and category["name"] not in tags:
            tags.append(category["name"])

        results.append(
            {
                "source": "loverslab",
                "remote_id": remote_id,
                "title": title,
                "author": author,
                "category": category.get("name", ""),
                "tags": tags,
                "page_url": page_url,
                "thumbnail_url": thumbnail_url,
                "updated_date": updated_date,
                "published_date": updated_date,
                "patreon_status": "NONE",
                "patreon_tier": "",
            }
        )

    return results, detected_pages
