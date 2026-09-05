from unittest.mock import MagicMock
from bs4 import BeautifulSoup

from src.providers.loverslab.downloader import (
    extract_download_candidates,
    download_loverslab_file,
)
from src.core.session_manager import SessionManager


def test_extract_download_candidates_scoring():
    html = """
    <div>
        <li data-rowid="1">
            <span class="ipsDataItem_title">MyAwesomeMod_v1.0.zip</span>
            <span class="ipsDataItem_meta">12.5 MB</span>
            <a href="/files/file/1-test/?do=download&r=123" data-action="download">Download</a>
        </li>
        <li data-rowid="2">
            <span class="ipsDataItem_title">ReadMe.txt</span>
            <span class="ipsDataItem_meta">5 KB</span>
            <a href="/files/file/1-test/?do=download&r=456" data-action="download">Download</a>
        </li>
        <li data-rowid="3">
            <span class="ipsDataItem_title">External Mirror Link</span>
            <span class="ipsDataItem_meta">External</span>
            <a href="https://mega.nz/file/xyz" data-action="download">Download</a>
        </li>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates = extract_download_candidates(soup, "https://www.loverslab.com")
    assert len(candidates) == 3
    # The zip candidate should have the highest score (100 for zip + 50 for MB size = 150)
    assert candidates[0]["title"] == "MyAwesomeMod_v1.0.zip"
    assert candidates[0]["score"] >= 150
    assert candidates[0]["url"] == "https://www.loverslab.com/files/file/1-test/?do=download&r=123"


def test_extract_download_candidates_fallback():
    html = """
    <div>
        <a class="ipsButton_primary" href="/files/file/1-test/?do=download&confirm=1">Télécharger</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates = extract_download_candidates(soup, "https://www.loverslab.com")
    assert len(candidates) == 1
    assert candidates[0]["url"] == "https://www.loverslab.com/files/file/1-test/?do=download&confirm=1"


def test_download_loverslab_file_patreon_delegation(tmp_path):
    mock_patreon = MagicMock()
    mock_patreon.download_mod_file.return_value = (True, "Téléchargé via Patreon")
    dest = tmp_path / "mod.zip"

    ok, msg = download_loverslab_file(
        "https://www.patreon.com/posts/12345",
        dest,
        patreon_provider=mock_patreon,
    )
    assert ok is True
    assert "Patreon" in msg
    mock_patreon.download_mod_file.assert_called_once()


def test_download_loverslab_file_external_hosted_detection(tmp_path, monkeypatch):
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/html"}
    mock_resp.url = "https://mega.nz/file/abc"
    mock_session.get.return_value = mock_resp

    monkeypatch.setattr(SessionManager, "get_http_session", lambda name: mock_session)
    monkeypatch.setattr(SessionManager, "is_member_authenticated", lambda name: True)

    dest = tmp_path / "mod.zip"
    ok, msg = download_loverslab_file(
        "https://www.loverslab.com/files/file/1-test/?do=download",
        dest,
        patreon_provider=None,
    )
    assert ok is False
    assert "hébergeur externe" in msg or "mega.nz" in msg


def test_download_loverslab_file_direct_success(tmp_path, monkeypatch):
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/zip", "Content-Length": "100"}
    mock_resp.url = "https://www.loverslab.com/files/download.zip"
    mock_resp.iter_content.return_value = [b"PK\x03\x04" + b"x" * 96]
    mock_session.get.return_value = mock_resp

    monkeypatch.setattr(SessionManager, "get_http_session", lambda name: mock_session)
    monkeypatch.setattr(SessionManager, "is_member_authenticated", lambda name: True)

    dest = tmp_path / "mod.zip"
    progress_calls = []

    def on_progress(pct, status, details):
        progress_calls.append((pct, status))

    ok, msg = download_loverslab_file(
        "https://www.loverslab.com/files/file/1-test/?do=download",
        dest,
        patreon_provider=None,
        progress_callback=on_progress,
    )
    assert ok is True
    assert dest.exists()
    assert dest.stat().st_size == 100
    assert len(progress_calls) > 0
