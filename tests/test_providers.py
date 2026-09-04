from src.providers.patreon import PatreonProvider
from src.providers.loverslab import LoversLabProvider


def test_patreon_post_id_extraction():
    url1 = "https://www.patreon.com/posts/wickedwhims-v180-102938475"
    assert PatreonProvider.extract_post_id(url1) == "102938475"

    url2 = "https://www.patreon.com/posts/102938475"
    assert PatreonProvider.extract_post_id(url2) == "102938475"

    url3 = "https://patreon.com/posts/12345?extra=param"
    assert PatreonProvider.extract_post_id(url3) == "12345"


def test_loverslab_provider_init():
    provider = LoversLabProvider()
    assert provider.provider_name == "loverslab"
    assert provider.base_url == "https://www.loverslab.com"
    assert "161-the-sims-4" in provider.category_url


def test_loverslab_get_mod_details_gallery_and_cleaning(monkeypatch):
    mock_html = """
    <html>
    <body>
        <div class="ipsCarousel">
            <ul class="cDownloadsCarousel">
                <li class="ipsCarousel_item">
                    <span class="ipsThumb" data-fullurl="https://static.loverslab.com/screenshots/main_cover.png">
                        <img src="https://static.loverslab.com/screenshots/main_cover.thumb.png" />
                    </span>
                </li>
            </ul>
        </div>
        <article>
            <div class="ipsType_richText">
                <p style="background-color:#0d0d0d; color:#999999; font-size:16px;">
                    House Details
                    <img src="/uploads/bedroom.png" />
                </p>
                <div class="ipsSpoiler">
                    <div class="ipsSpoiler_contents">
                        <img src="https://www.loverslab.com/uploads/bathroom.png" />
                    </div>
                </div>
                <p>
                    <a href="https://www.loverslab.com/uploads/patio.png">Voir le patio</a>
                </p>
            </div>
        </article>
    </body>
    </html>
    """

    class MockResponse:
        status_code = 200
        text = mock_html
        headers = {}

    class MockSession:
        def get(self, url, **kwargs):
            return MockResponse()

    monkeypatch.setattr("src.core.session_manager.SessionManager.get_http_session", lambda name: MockSession())

    provider = LoversLabProvider()
    details = provider.get_mod_details("https://www.loverslab.com/files/file/12345-sample-mod/")

    desc = details["description"]
    assert "mod-gallery" in desc
    assert "main_cover.png" in desc
    assert "bedroom.png" in desc
    assert "bathroom.png" in desc
    assert "patio.png" in desc
    # Cleaned dark background
    assert "background-color:#0d0d0d" not in desc


def test_image_format_detection():
    from src.ui.components.mod_detail_modal import DescriptionFetchWorker

    worker = DescriptionFetchWorker(1)
    html = """
    <div>
        <img src="http://example.com/pic1.png" />
    </div>
    """
    # Verify resolve_images handles parsing without error
    res = worker._resolve_images(html)
    assert "<img" in res

