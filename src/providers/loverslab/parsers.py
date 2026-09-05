import copy
import re
from typing import List, Tuple
from bs4 import BeautifulSoup


def extract_gallery_screenshots(soup: BeautifulSoup, base_url: str = "https://www.loverslab.com") -> List[str]:
    """
    Extracts high-resolution screenshots from LoversLab mod file pages
    (carousel items, lightbox elements, and screenshot links).
    """
    gallery_screenshots: List[str] = []
    carousel_candidates = []

    art_elem = soup.select_one("article")
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
                    u = f"{base_url}{u}"
                if u.startswith("http") and not any(
                    j in u.lower() for j in ["/themes/", "/reactions/", "icon_", "avatar", "logo", ".svg"]
                ):
                    if u not in gallery_screenshots:
                        gallery_screenshots.append(u)

    for a in soup.select(
        "a[data-ipsLightbox], a[href*='/screenshots/'], .cFileTop a[href$='.jpg'], .cFileTop a[href$='.png'], .cFileTop a[href$='.webp']"
    ):
        h = a.get("href")
        if h and h.startswith("http") and not any(
            j in h.lower() for j in ["/themes/", "/reactions/", "icon_", "avatar", "logo", ".svg"]
        ):
            if h not in gallery_screenshots:
                gallery_screenshots.append(h)

    return gallery_screenshots


def sanitize_description_html(content_elem, base_url: str = "https://www.loverslab.com") -> Tuple[str, List[str]]:
    """
    Cleans inline scripts, styles, author formatting clashes, decomposes junk elements,
    and returns sanitized inner HTML along with list of inline image URLs.
    """
    clean_elem = copy.deepcopy(content_elem)
    for junk in clean_elem.select(
        ".cFileChangelog, [data-role='changelog'], div#changeLogData, .ipsMenu, script, style, iframe, form, button, input, noscript, h2, hr, p.ipsType_light"
    ):
        junk.decompose()

    # Clean author inline styles to avoid dark-mode color clashes
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
                src = f"{base_url}{src}"
            img["src"] = src
            body_imgs.append(src)
        for attr in ["data-ratio", "data-fileid", "srcset", "sizes", "class", "loading"]:
            if attr in img.attrs:
                del img.attrs[attr]
        img["style"] = "max-width: 95%; height: auto; border-radius: 8px; margin: 10px auto; display: block;"

    # Process links for absolute URLs
    for a in clean_elem.select("a"):
        href = a.get("href", "")
        if href and href.startswith("/"):
            a["href"] = f"{base_url}{href}"
        a["style"] = "color: #ff2d87; text-decoration: underline;"

    return clean_elem.decode_contents().strip(), body_imgs
