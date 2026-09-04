from unittest.mock import patch, MagicMock
from src.providers.loverslab import LoversLabProvider


def test_loverslab_patreon_detection_21703():
    """Mod 21703 has a Patreon profile link in description but is a direct LoversLab mod."""
    provider = LoversLabProvider()
    url = "https://www.loverslab.com/files/file/21703-ger-kritical-dreams-of-surrender-objekte-deutsche-%C3%BCbersetzungen/"
    details = provider.get_mod_details(url)
    assert details["patreon_status"] == "NONE", f"Expected NONE, got {details['patreon_status']}"
    assert any("loverslab.com" in d["url"] for d in details["download_urls"])


def test_loverslab_patreon_detection_51253():
    """Mod 51253 has a Patreon tip jar in description but is a direct LoversLab mod."""
    provider = LoversLabProvider()
    url = "https://www.loverslab.com/files/file/51253-dislike-oral/"
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
    mods = provider.scrape_catalog(page=1)
    assert len(mods) > 0
    for m in mods:
        assert m["title"] and m["title"].strip() != "", f"Empty title found for mod {m['remote_id']}"
        assert m["page_url"].startswith("http")
