"""
Report-related asynchronous background workers for Qt UI.
"""
from PySide6.QtCore import Signal

from src.api.client import get_api_client
from src.utils.logger import logger
from src.utils.thread_utils import BaseWorker


class SubmitReportWorker(BaseWorker):
    """Asynchronous worker to submit the forum report via API."""

    finished_result = Signal(bool, str, str)  # success, message, reported_at

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload

    def run(self):
        self._is_running = True
        client = get_api_client()
        try:
            if self._is_cancelled:
                return
            res = client.report_missing_requirements(self.payload)
            success = res.get("success", False)
            msg = res.get("message", "")
            reported_at = res.get("reported_at", "à l'instant")
            if not self._is_cancelled:
                self.finished_result.emit(success, msg, reported_at)
        except Exception as e:
            if not self._is_cancelled:
                logger.error(f"SubmitReportWorker error: {e}")
                self.finished_result.emit(False, str(e), "")
        finally:
            self._is_running = False


class CheckReportStatusWorker(BaseWorker):
    """Asynchronous worker to check missing report status from API."""
    status_ready = Signal(dict)

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload

    def run(self):
        self._is_running = True
        try:
            if self._is_cancelled:
                return
            client = get_api_client()
            res = client.check_missing_report(self.payload)
            if not self._is_cancelled:
                self.status_ready.emit(res)
        except Exception as e:
            if not self._is_cancelled:
                logger.debug(f"CheckReportStatusWorker error: {e}")
                self.status_ready.emit({
                    "can_report": True,
                    "already_reported": False,
                    "reported_at": None,
                    "formatted_message": "",
                    "author": self.payload.get("author", ""),
                    "is_authenticated": True,
                })
        finally:
            self._is_running = False
