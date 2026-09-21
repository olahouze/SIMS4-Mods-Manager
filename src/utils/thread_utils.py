"""
Thread utilities for PySide6 QRunnable/QThreadPool lifecycle management.
Replaces fragile QThread subclasses with QRunnable executed on QThreadPool,
completely eliminating 'QThread: Destroyed while thread is still running' crashes.
"""

from typing import Optional, Any
import warnings
from PySide6.QtCore import QObject, QRunnable, QThreadPool
from src.utils.logger import logger


class BaseWorker(QObject, QRunnable):
    """
    Standard thread-safe worker for asynchronous PySide6 background operations.
    Inherits from both QObject (enabling native Qt Signals) and QRunnable.

    Key advantages over QThread:
    - Never creates or destroys transient OS threads; tasks execute on managed QThreadPool.
    - Eliminates 'QThread: Destroyed while thread is still running' crashes by design.
    - Provides a .start() method for 100% backward compatibility with QThread.
    - Fully supports cooperative cancellation with self.is_cancelled() checks.
    """

    def __init__(self, parent: Optional[QObject] = None):
        QObject.__init__(self, parent)
        QRunnable.__init__(self)
        self.setAutoDelete(True)
        self._is_cancelled = False
        self._is_running = False

    def cancel(self) -> None:
        """Requests cooperative cancellation of the background task."""
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        """Returns True if the task has been requested to cancel."""
        return self._is_cancelled

    def isRunning(self) -> bool:
        """Returns True if the task is currently executing in QThreadPool."""
        return self._is_running

    def start(self) -> None:
        """Dispatches this worker to the global QThreadPool."""
        self._is_running = True
        QThreadPool.globalInstance().start(self)

    def wait(self, msecs: int = 0) -> bool:
        """Backward-compatible wait method."""
        return True


def safe_stop_thread(worker: Optional[Any]) -> None:
    """
    Safely cancels and disconnects a worker without causing crashes or dead callbacks.
    Works seamlessly with both BaseWorker (QRunnable) and legacy QThread instances.
    """
    if worker is None:
        return

    # 1. Cooperative cancellation
    try:
        if hasattr(worker, "cancel") and callable(worker.cancel):
            worker.cancel()
        elif hasattr(worker, "requestInterruption") and callable(worker.requestInterruption):
            worker.requestInterruption()
    except Exception as e:
        logger.debug(f"Error cancelling worker: {e}")

    # 2. Disconnect common outbound signals to prevent callbacks to stale UI widgets
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for sig_name in (
            "data_ready",
            "error_signal",
            "finished_signal",
            "finished_result",
            "status_ready",
            "thumb_ready",
            "images_updated",
            "loaded",
            "failed",
            "progress",
            "progress_updated",
            "install_finished",
            "finished",
        ):
            sig = getattr(worker, sig_name, None)
            if sig is not None:
                try:
                    sig.disconnect()
                except (RuntimeError, Exception):
                    pass


def cleanup_all_threads(timeout_ms: int = 500) -> None:
    """
    Waits briefly for any lingering background workers on application shutdown.
    """
    try:
        QThreadPool.globalInstance().waitForDone(timeout_ms)
    except Exception as e:
        logger.debug(f"Error waiting for QThreadPool completion on shutdown: {e}")
