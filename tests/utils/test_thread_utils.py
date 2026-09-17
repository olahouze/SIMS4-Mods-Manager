"""
Unit tests for thread_utils.py, BaseWorker, and safe_stop_thread lifecycle management.
"""
import time
from PySide6.QtCore import Signal, QThreadPool
from src.utils.thread_utils import BaseWorker, safe_stop_thread, cleanup_all_threads


class MockWorker(BaseWorker):
    data_ready = Signal(str)

    def __init__(self):
        super().__init__()
        self.ran = False

    def run(self):
        self._is_running = True
        try:
            for _ in range(10):
                if self._is_cancelled:
                    return
                time.sleep(0.01)
            self.ran = True
            if not self._is_cancelled:
                self.data_ready.emit("done")
        finally:
            self._is_running = False


def test_safe_stop_thread_none():
    """Verify safe_stop_thread handles None without error."""
    safe_stop_thread(None)


def test_base_worker_lifecycle(qapp):
    """Verify BaseWorker executes properly and signals correctly."""
    worker = MockWorker()
    received = []
    worker.data_ready.connect(lambda msg: received.append(msg))

    worker.run()
    assert worker.ran is True
    assert received == ["done"]


def test_base_worker_cancellation(qapp):
    """Verify BaseWorker cancels gracefully when requested."""
    worker = MockWorker()
    received = []
    worker.data_ready.connect(lambda msg: received.append(msg))

    worker.cancel()
    assert worker.is_cancelled() is True
    worker.run()
    assert worker.ran is False
    assert len(received) == 0


def test_safe_stop_thread_running_worker(qapp):
    """Verify safe_stop_thread cancels and disconnects signals on a running worker."""
    worker = MockWorker()
    received = []
    worker.data_ready.connect(lambda msg: received.append(msg))

    worker.start()
    assert worker.isRunning()

    safe_stop_thread(worker)
    assert worker.is_cancelled() is True

    # Wait for the QThreadPool task to complete
    QThreadPool.globalInstance().waitForDone(500)
    assert not worker.isRunning()
    # Signal was disconnected before emission, so no callbacks
    assert len(received) == 0


def test_cleanup_all_threads(qapp):
    """Verify cleanup_all_threads waits for QThreadPool without errors."""
    worker = MockWorker()
    worker.start()
    cleanup_all_threads(timeout_ms=500)
    assert not worker.isRunning()
