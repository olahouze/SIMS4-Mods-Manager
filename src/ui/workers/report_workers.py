"""
Report-related asynchronous background worker threads for Qt UI.
"""
from PySide6.QtCore import QThread, Signal

from src.api.client import get_api_client
from src.utils.logger import logger


class SubmitReportWorker(QThread):
    """Asynchronous worker to submit the forum report via API."""

    finished_result = Signal(bool, str, str)  # success, message, reported_at

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload
        self.finished.connect(self.deleteLater)

    def run(self):
        client = get_api_client()
        try:
            res = client.report_missing_requirements(self.payload)
            success = res.get("success", False)
            msg = res.get("message", "")
            reported_at = res.get("reported_at", "à l'instant")
            self.finished_result.emit(success, msg, reported_at)
        except Exception as e:
            logger.error(f"SubmitReportWorker error: {e}")
            self.finished_result.emit(False, str(e), "")


class CheckReportStatusWorker(QThread):
    """Asynchronous worker to check missing report status from API."""
    status_ready = Signal(dict)

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload
        self.finished.connect(self.deleteLater)

    def run(self):
        try:
            client = get_api_client()
            res = client.check_missing_report(self.payload)
            self.status_ready.emit(res)
        except Exception as e:
            logger.debug(f"CheckReportStatusWorker error: {e}")
            self.status_ready.emit({
                "can_report": True,
                "already_reported": False,
                "reported_at": None,
                "formatted_message": "",
                "author": self.payload.get("author", ""),
                "is_authenticated": True,
            })

