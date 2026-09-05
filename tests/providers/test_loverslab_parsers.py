from bs4 import BeautifulSoup
from src.providers.loverslab.parsers import extract_gallery_screenshots, sanitize_description_html


def test_extract_gallery_screenshots_carousel_and_lightbox():
    html = """
    <div class="cFileTop">
        <div class="ipsCarousel">
            <ul>
                <li data-fullurl="https://www.loverslab.com/uploads/monthly_2024/screen1.jpg"></li>
                <li><img src="https://www.loverslab.com/uploads/monthly_2024/screen2.png" /></li>
                <li><img src="https://www.loverslab.com/uploads/monthly_2024/avatar_user.png" /></li>
            </ul>
        </div>
        <a href="https://www.loverslab.com/uploads/monthly_2024/screen3.webp" data-ipsLightbox>Zoom</a>
    </div>
    <article><p>Description</p></article>
    """
    soup = BeautifulSoup(html, "html.parser")
    screenshots = extract_gallery_screenshots(soup, "https://www.loverslab.com")

    assert "https://www.loverslab.com/uploads/monthly_2024/screen1.jpg" in screenshots
    assert "https://www.loverslab.com/uploads/monthly_2024/screen2.png" in screenshots
    assert "https://www.loverslab.com/uploads/monthly_2024/screen3.webp" in screenshots
    # Avatars must be excluded
    assert not any("avatar" in s for s in screenshots)


def test_sanitize_description_html_strips_scripts_and_cleans_styles():
    html = """
    <div class="ipsType_richText" style="background-color: #000; color: #fff;">
        <script>alert('malicious')</script>
        <div class="cFileChangelog">Old version notes</div>
        <p style="background: red; color: yellow;">Welcome to the mod</p>
        <img src="/uploads/images/sample.jpg" data-ratio="16/9" />
        <a href="/files/file/123-dep/">Dependency Mod</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    content_elem = soup.select_one(".ipsType_richText")
    clean_html, body_imgs = sanitize_description_html(content_elem, "https://www.loverslab.com")

    assert "<script" not in clean_html
    assert "cFileChangelog" not in clean_html
    assert "background-color" not in clean_html
    assert "background: red" not in clean_html
    # Image src was resolved to absolute URL
    assert "https://www.loverslab.com/uploads/images/sample.jpg" in body_imgs
    assert 'src="https://www.loverslab.com/uploads/images/sample.jpg"' in clean_html
    # Link was resolved to absolute URL
    assert 'href="https://www.loverslab.com/files/file/123-dep/"' in clean_html
