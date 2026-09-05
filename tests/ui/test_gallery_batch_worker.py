from unittest.mock import MagicMock
from PySide6.QtGui import QImage, QColor

from src.ui.workers.detail_workers import GalleryBatchWorker
from src.ui.views.mod_detail_view import ModDetailView
from src.core.session_manager import SessionManager


def create_test_image_bytes() -> bytes:
    """Helper creating a minimal valid JPEG/PNG in-memory image."""
    img = QImage(100, 100, QImage.Format.Format_RGB32)
    img.fill(QColor(255, 0, 0))
    from PySide6.QtCore import QBuffer, QIODevice
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "JPG")
    return bytes(buf.data())


def test_gallery_batch_worker_disk_and_memory_cache(qapp, tmp_path):
    """Verifies that GalleryBatchWorker checks memory and disk cache first without network calls."""
    cache_dir = tmp_path / "cache_thumbs"
    cache_dir.mkdir()

    img_bytes = create_test_image_bytes()
    test_url = "https://example.com/screenshot1.jpg"

    # Save to disk cache manually
    import hashlib
    u_hash = hashlib.md5(test_url.encode("utf-8")).hexdigest()
    cached_file = cache_dir / f"thumb_{u_hash}.jpg"
    cached_file.write_bytes(img_bytes)

    received_pixmaps = []

    worker = GalleryBatchWorker([test_url], cache_dir, load_id=1)
    worker.thumb_ready.connect(lambda idx, pix: received_pixmaps.append((idx, pix)))
    worker.run()  # synchronous execution for test

    assert len(received_pixmaps) == 1
    idx, pix = received_pixmaps[0]
    assert idx == 0
    assert not pix.isNull()
    assert test_url in GalleryBatchWorker._PIXMAP_CACHE

    # Second run: hits in-memory cache directly
    received_pixmaps.clear()
    worker2 = GalleryBatchWorker([test_url], cache_dir, load_id=2)
    worker2.thumb_ready.connect(lambda idx, pix: received_pixmaps.append((idx, pix)))
    worker2.run()
    assert len(received_pixmaps) == 1


def test_gallery_batch_worker_parallel_network_fetch(qapp, tmp_path, monkeypatch):
    """Verifies concurrent downloads with shared session and ThreadPoolExecutor."""
    cache_dir = tmp_path / "cache_network"
    cache_dir.mkdir()

    img_bytes = create_test_image_bytes()
    urls = [
        "https://example.com/net_pic_1.jpg",
        "https://example.com/net_pic_2.jpg",
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = img_bytes

    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp

    monkeypatch.setattr(SessionManager, "get_http_session", lambda name: mock_session)

    # Clear memory cache for these urls
    for u in urls:
        GalleryBatchWorker._PIXMAP_CACHE.pop(u, None)

    received = []
    worker = GalleryBatchWorker(urls, cache_dir, load_id=1)
    worker.thumb_ready.connect(lambda idx, pix: received.append((idx, pix)))
    worker.run()

    assert len(received) == 2
    assert mock_session.get.call_count == 2


def test_gallery_batch_worker_cancellation(qapp, tmp_path):
    """Verifies cooperative cancellation."""
    cache_dir = tmp_path / "cache_cancel"
    cache_dir.mkdir()

    urls = ["https://example.com/cancel_pic.jpg"]
    worker = GalleryBatchWorker(urls, cache_dir, load_id=1)
    worker.cancel()
    assert worker._is_cancelled is True

    received = []
    worker.thumb_ready.connect(lambda idx, pix: received.append(idx))
    worker.run()
    assert len(received) == 0


def test_mod_detail_view_immediate_reset_and_race_guard(qapp, monkeypatch):
    """Verifies that ModDetailView immediately resets the UI state on load_mod and protects against race conditions."""
    from src.ui.workers import FetchDetailsWorker
    monkeypatch.setattr(FetchDetailsWorker, "start", lambda self: None)

    view = ModDetailView()

    try:
        # Pre-populate view with "Mod 1"
        mod1 = {
            "id": 101,
            "title": "Old Mod 1",
            "author": "Author 1",
            "description": "<p>Old Description of Mod 1</p>",
            "requirements_text": "Old Req",
        }
        view.load_mod(mod1)
        # Simulate fetch completed for mod 1
        view._on_details_fetched({
            "title": "Old Mod 1",
            "description": "<p>Old Description of Mod 1</p>",
            "screenshots": ["https://example.com/old.jpg"],
        }, load_id=view._current_load_id)

        assert "Old Description of Mod 1" in view.desc_browser.toHtml()

        # Now load "Mod 2"
        mod2 = {
            "id": 102,
            "title": "New Mod 2",
            "author": "Author 2",
        }
        view.load_mod(mod2)

        # 1. UI is immediately reset
        html_after_reset = view.desc_browser.toHtml()
        assert "Old Description of Mod 1" not in html_after_reset
        assert "Chargement des détails" in html_after_reset
        assert view.title_lbl.text() == "New Mod 2"
        assert view.meta_author.text() == "👤 Auteur : Author 2"

        # 2. Obsolete callback from Mod 1 is ignored
        view._on_details_fetched({
            "title": "Old Mod 1 Delayed",
            "description": "<p>Late Old Description</p>",
        }, load_id=1)

        # Should still show loading state, not the late description
        assert "Late Old Description" not in view.desc_browser.toHtml()

        # 3. Proper callback with matching load_id is accepted
        view._on_details_fetched({
            "title": "New Mod 2",
            "description": "<p>Fresh Description for Mod 2</p>",
            "screenshots": [],
        }, load_id=view._current_load_id)

        assert "Fresh Description for Mod 2" in view.desc_browser.toHtml()

    finally:
        view.deleteLater()
        qapp.processEvents()
