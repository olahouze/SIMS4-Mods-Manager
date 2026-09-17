"""
Stress tests for background worker lifecycle and garbage collection under load.
Ensures that abandoning, replacing, and cancelling workers in rapid succession
never causes crashes or 'QThread: Destroyed while thread is still running'.
"""
import time
from unittest.mock import MagicMock
from PySide6.QtCore import Signal, QThreadPool
from src.utils.thread_utils import BaseWorker, safe_stop_thread
from src.ui.views.catalog_view import CatalogView
from src.ui.views.mod_detail_view import ModDetailView


class HeavyWorker(BaseWorker):
    done_signal = Signal(int)

    def __init__(self, item_id: int):
        super().__init__()
        self.item_id = item_id

    def run(self):
        self._is_running = True
        try:
            for _ in range(5):
                if self._is_cancelled:
                    return
                time.sleep(0.02)
            if not self._is_cancelled:
                self.done_signal.emit(self.item_id)
        finally:
            self._is_running = False


def test_stress_rapid_worker_abandonment(qapp):
    """
    Stress test: rapidly start 25 workers, cancel them and immediately
    orphan their Python references to trigger garbage collection while running.
    """
    received = []
    for i in range(25):
        w = HeavyWorker(i)
        w.done_signal.connect(lambda val: received.append(val))
        w.start()
        # Immediately safe stop and drop reference
        safe_stop_thread(w)
        w = None

    # Wait for pool to drain without any crashes
    QThreadPool.globalInstance().waitForDone(2000)
    assert len(received) == 0


def test_stress_catalog_rapid_refresh(qapp, monkeypatch):
    """
    Simulates rapid incoming refresh events (like live scraping page completions)
    while previous CatalogFetchWorkers are still active.
    """
    mock_api = MagicMock()
    mock_api.get_accounts.return_value = []
    mock_api.get_catalog.return_value = {"items": [], "total": 0}

    cat_view = CatalogView()
    cat_view.api_client = mock_api

    # Fire 15 rapid refreshes
    for _i in range(15):
        cat_view.refresh_catalog()

    # Drain pool
    QThreadPool.globalInstance().waitForDone(2000)
    assert cat_view._fetch_id >= 15


def test_stress_mod_detail_rapid_loads(qapp, monkeypatch):
    """
    Simulates rapid clicking through mods in ModDetailView while FetchDetailsWorker
    is running in the background.
    """
    mock_api = MagicMock()
    mock_api.get_catalog_mod_details.return_value = {
        "title": "Stress Mod",
        "description": "<p>Content</p>",
        "screenshots": [],
    }
    monkeypatch.setattr("src.ui.workers.detail_workers.get_api_client", lambda: mock_api)

    detail_view = ModDetailView()

    for i in range(15):
        mod_data = {
            "id": i + 1,
            "title": f"Mod {i + 1}",
            "author": f"Author {i + 1}",
            "source": "loverslab",
        }
        detail_view.load_mod(mod_data)

    QThreadPool.globalInstance().waitForDone(2000)
    detail_view.cleanup()
