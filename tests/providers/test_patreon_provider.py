from unittest.mock import MagicMock
from src.providers.patreon import PatreonProvider
from src.core.session_manager import SessionManager


def test_patreon_post_id_extraction():
    url1 = "https://www.patreon.com/posts/wickedwhims-v180-102938475"
    assert PatreonProvider.extract_post_id(url1) == "102938475"

    url2 = "https://www.patreon.com/posts/102938475"
    assert PatreonProvider.extract_post_id(url2) == "102938475"

    url3 = "https://patreon.com/posts/12345?extra=param"
    assert PatreonProvider.extract_post_id(url3) == "12345"

    assert PatreonProvider.extract_post_id("https://patreon.com/creator") is None


def test_patreon_check_post_access_public(monkeypatch):
    provider = PatreonProvider()
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "attributes": {
                "title": "Public Patreon Mod",
                "current_user_can_view": True,
                "min_cents_pledged_to_view": 0,
                "published_at": "2026-01-01T00:00:00Z",
                "post_file": {"name": "mod.zip", "url": "https://patreon.com/file/mod.zip", "size": 1024},
                "content": '<a href="https://mega.nz/file/xyz">Mirror</a>',
            }
        },
        "included": [],
    }
    mock_session.get.return_value = mock_resp
    monkeypatch.setattr(SessionManager, "get_http_session", lambda name: mock_session)

    res = provider.check_post_access("https://www.patreon.com/posts/12345")
    assert res["status"] == "PUBLIC"
    assert res["can_view"] is True
    assert res["title"] == "Public Patreon Mod"
    assert len(res["download_urls"]) == 1
    assert res["download_urls"][0]["name"] == "mod.zip"
    assert len(res["external_links"]) == 1
    assert "mega.nz" in res["external_links"][0]


def test_patreon_check_post_access_locked(monkeypatch):
    provider = PatreonProvider()
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "attributes": {
                "title": "Tier Mod",
                "current_user_can_view": False,
                "min_cents_pledged_to_view": 500,
                "post_file": None,
                "content": "",
            }
        },
        "included": [],
    }
    mock_session.get.return_value = mock_resp
    monkeypatch.setattr(SessionManager, "get_http_session", lambda name: mock_session)

    res = provider.check_post_access("https://www.patreon.com/posts/12345")
    assert res["status"] == "LOCKED"
    assert res["can_view"] is False
    assert res["tier_str"] == "$5.00/mois"


def test_patreon_scrape_catalog_and_interfaces():
    provider = PatreonProvider()
    assert provider.scrape_catalog() == []
    assert provider.check_access({"page_url": "invalid"}) == "UNKNOWN"


def test_patreon_download_mod_file_image_rejection(tmp_path, monkeypatch):
    provider = PatreonProvider()
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "image/jpeg"}
    mock_session.get.return_value = mock_resp
    monkeypatch.setattr(SessionManager, "get_http_session", lambda name: mock_session)

    dest = tmp_path / "mod.zip"
    ok, msg = provider.download_mod_file("https://patreon.com/preview.jpg", dest)
    assert ok is False
    assert "image de prévisualisation" in msg


def test_patreon_download_mod_file_success(tmp_path, monkeypatch):
    provider = PatreonProvider()
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/octet-stream", "Content-Length": "50"}
    mock_resp.iter_content.return_value = [b"x" * 50]
    mock_session.get.return_value = mock_resp
    monkeypatch.setattr(SessionManager, "get_http_session", lambda name: mock_session)

    dest = tmp_path / "mod.zip"
    ok, msg = provider.download_mod_file("https://patreon.com/file.zip", dest)
    assert ok is True
    assert dest.exists()
    assert dest.stat().st_size == 50
