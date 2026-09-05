from unittest.mock import patch, MagicMock
from src.providers.loverslab import LoversLabProvider


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


def test_loverslab_patreon_detection_21703():
    """Mod 21703 has a Patreon profile link in description but is a direct LoversLab mod."""
    provider = LoversLabProvider()
    url = "https://www.loverslab.com/files/file/21703-sample/"

    def mock_get(u, *args, **kwargs):
        resp = MagicMock()
        if "?do=download" in u:
            resp.status_code = 200
            resp.headers = {}
        else:
            resp.status_code = 200
            resp.text = '<html><article><a href="https://www.patreon.com/kritical">Patreon Profile</a></article></html>'
            resp.headers = {}
        return resp

    with patch("src.core.session_manager.SessionManager.get_http_session") as mock_get_sess:
        sess_mock = MagicMock()
        sess_mock.get.side_effect = mock_get
        mock_get_sess.return_value = sess_mock
        details = provider.get_mod_details(url)
        assert details["patreon_status"] == "NONE", f"Expected NONE, got {details['patreon_status']}"
        assert any("loverslab.com" in d["url"] for d in details["download_urls"])


def test_loverslab_patreon_detection_51253():
    """Mod 51253 has a Patreon tip jar in description but is a direct LoversLab mod."""
    provider = LoversLabProvider()
    url = "https://www.loverslab.com/files/file/51253-sample/"

    def mock_get(u, *args, **kwargs):
        resp = MagicMock()
        if "?do=download" in u:
            resp.status_code = 200
            resp.headers = {}
        else:
            resp.status_code = 200
            resp.text = '<html><article><a href="https://www.patreon.com/author">Tip Jar</a></article></html>'
            resp.headers = {}
        return resp

    with patch("src.core.session_manager.SessionManager.get_http_session") as mock_get_sess:
        sess_mock = MagicMock()
        sess_mock.get.side_effect = mock_get
        mock_get_sess.return_value = sess_mock
        details = provider.get_mod_details(url)
        assert details["patreon_status"] == "NONE", f"Expected NONE, got {details['patreon_status']}"
        assert any("loverslab.com" in d["url"] for d in details["download_urls"])


def test_loverslab_patreon_detection_51251():
    """Mod 51251 redirects to a Patreon post for download when authenticated."""
    provider = LoversLabProvider()
    url = "https://www.loverslab.com/files/file/51251-marigold-ts4_lolia-set/"

    def mock_get(u, *args, **kwargs):
        resp = MagicMock()
        if "?do=download" in u:
            resp.status_code = 301
            resp.headers = {"Location": "https://www.patreon.com/Marigoldsims/posts/marigold-ts4-set-143719297"}
        else:
            resp.status_code = 200
            resp.text = "<html><article>Marigold CC</article></html>"
            resp.headers = {}
        return resp

    with patch("src.core.session_manager.SessionManager.get_http_session") as mock_get_sess:
        sess_mock = MagicMock()
        sess_mock.get.side_effect = mock_get
        mock_get_sess.return_value = sess_mock
        details = provider.get_mod_details(url)
        assert details["patreon_status"] in ["PUBLIC", "UNLOCKED", "LOCKED"]
        assert any("patreon" in d["url"].lower() for d in details["download_urls"])


def test_loverslab_scrape_page1_titles():
    """LoversLab catalog scraping must extract valid non-empty titles for all items."""
    provider = LoversLabProvider()

    def mock_get(u, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = '''
        <html>
            <li class="ipsDataItem" data-rowid="1234">
                <h4 class="ipsDataItem_title"><a href="https://www.loverslab.com/files/file/1234-mod-one/">Mod One</a></h4>
                <div class="ipsDataItem_meta"><a href="/profile/1">Author1</a></div>
            </li>
            <li class="ipsDataItem" data-rowid="5678">
                <h4 class="ipsDataItem_title"><a href="https://www.loverslab.com/files/file/5678-mod-two/">Mod Two</a></h4>
                <div class="ipsDataItem_meta"><a href="/profile/2">Author2</a></div>
            </li>
        </html>
        '''
        return resp

    with patch("src.core.session_manager.SessionManager.get_http_session") as mock_get_sess:
        sess_mock = MagicMock()
        sess_mock.get.side_effect = mock_get
        mock_get_sess.return_value = sess_mock
        mods = provider.scrape_catalog(page=1)
        assert len(mods) == 2
        for m in mods:
            assert m["title"] and m["title"].strip() != "", f"Empty title found for mod {m['remote_id']}"
            assert m["page_url"].startswith("http")


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
