from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
import pytest

from src.ui.workers import (
    SyncTriggerWorker,
    InstallWorker,
    FetchDetailsWorker,
    GalleryThumbWorker,
    DescriptionImageLoaderWorker,
)
from src.core.session_manager import SessionManager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_sync_trigger_worker(qapp):
    mock_api = MagicMock()
    worker = SyncTriggerWorker(mock_api, max_pages=3)
    results = []
    worker.finished_signal.connect(lambda ok, msg: results.append((ok, msg)))

    # Run directly
    worker.run()
    assert len(results) == 1
    assert results[0] == (True, "OK")
    mock_api.start_catalog_sync.assert_called_once_with(max_pages=3)

    # Test failure path
    mock_api.start_catalog_sync.side_effect = RuntimeError("Network down")
    results.clear()
    worker.run()
    assert len(results) == 1
    assert results[0][0] is False
    assert "Network down" in results[0][1]


def test_install_worker(qapp, monkeypatch):
    mock_api = MagicMock()
    mock_api.install_mod_stream.return_value = [
        {"type": "progress", "percent": 50, "status": "Downloading...", "details": "10 MB"},
        {"type": "finished", "success": True, "message": "Installed"},
    ]
    monkeypatch.setattr("src.ui.workers.catalog_workers.get_api_client", lambda: mock_api)

    worker = InstallWorker({"id": 1, "title": "Test Mod"})
    progress_calls = []
    finished_calls = []
    worker.progress.connect(lambda pct, st, det: progress_calls.append((pct, st, det)))
    worker.finished.connect(lambda ok, msg: finished_calls.append((ok, msg)))

    worker.run()
    assert len(progress_calls) >= 2  # init progress + stream progress
    assert progress_calls[-1][0] == 50
    assert len(finished_calls) == 1
    assert finished_calls[0] == (True, "Installed")


def test_fetch_details_worker_by_id(qapp, monkeypatch):
    mock_api = MagicMock()
    mock_api.get_catalog_mod_details.return_value = {"id": 10, "title": "Direct Mod Details"}
    monkeypatch.setattr("src.ui.workers.detail_workers.get_api_client", lambda: mock_api)

    worker = FetchDetailsWorker(mod_id=10, page_url=None, source="loverslab", remote_id="100")
    results = []
    worker.finished.connect(lambda data: results.append(data))

    worker.run()
    assert len(results) == 1
    assert results[0]["title"] == "Direct Mod Details"


def test_gallery_thumb_worker(qapp, tmp_path, monkeypatch):
    cache_dir = tmp_path / "thumbs"
    worker = GalleryThumbWorker(index=0, url="https://example.com/thumb.jpg", cache_dir=cache_dir)

    # Generate a valid 10x10 PNG byte array using QImage
    from PySide6.QtGui import QImage
    from PySide6.QtCore import QBuffer, QIODevice

    img = QImage(10, 10, QImage.Format.Format_RGB32)
    img.fill(0xFF0000)
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    valid_png = bytes(buf.data())

    # Mock session
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = valid_png
    mock_session.get.return_value = mock_resp
    monkeypatch.setattr(SessionManager, "get_http_session", lambda name: mock_session)

    ready_results = []
    worker.thumb_ready.connect(lambda idx, pix: ready_results.append((idx, pix)))

    worker.run()
    assert len(ready_results) == 1
    assert ready_results[0][0] == 0
    assert not ready_results[0][1].isNull()


def test_description_image_loader_worker_cancel(qapp):
    html = '<p><img src="https://example.com/img1.png"></p>'
    worker = DescriptionImageLoaderWorker(raw_html=html)
    worker.cancel()
    assert worker._is_cancelled is True
    # run should not throw and return early
    worker.run()
