"""
Unified AuthorInterpellateWidget managing the creator interpellation button,
asynchronous status checking, dynamic styling, and opening ReportPreviewDialog.
Shared between ModDetailView and DependenciesDialog.
"""
from typing import Optional, List
from PySide6.QtCore import Signal, QThread
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QMessageBox

from src.api.client import get_api_client
from src.ui.components.report_preview_dialog import ReportPreviewDialog
from src.i18n import tr
from src.utils.logger import logger


class CheckReportStatusWorker(QThread):
    status_ready = Signal(dict)

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload

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
                "formatted_message": "",
                "author": self.payload.get("author", ""),
                "is_authenticated": True,
            })


class AuthorInterpellateWidget(QWidget):
    """
    Reusable button component for creator interpellation with live status checking
    and bidirectional override synchronization.
    """
    override_changed = Signal(str, str)
    report_sent = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._check_worker: Optional[CheckReportStatusWorker] = None
        self._status_result: Optional[dict] = None
        self._mod_data: dict = {}
        self._missing_modules: List[str] = []
        self._unnecessary_modules: List[str] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.btn_report = QPushButton(tr("dependencies.btn_report_author"))
        self.btn_report.setFixedHeight(30)
        self.btn_report.clicked.connect(self._on_clicked)
        self._apply_checking_style()
        layout.addWidget(self.btn_report)

    def check_status(
        self,
        mod_data: dict,
        missing_modules: List[str],
        unnecessary_modules: List[str],
    ):
        """Starts asynchronous check of report status for this mod."""
        self._mod_data = mod_data
        self._missing_modules = list(missing_modules or [])
        self._unnecessary_modules = list(unnecessary_modules or [])

        if self._check_worker and self._check_worker.isRunning():
            try:
                self._check_worker.status_ready.disconnect()
            except Exception:
                pass
            self._check_worker.terminate()
            self._check_worker = None

        cat_id = mod_data.get("id") or mod_data.get("catalog_mod_id")
        remote_id = str(mod_data.get("remote_id", ""))
        page_url = mod_data.get("page_url", "")
        source = mod_data.get("source", "loverslab")
        mod_title = mod_data.get("title", "")
        author = mod_data.get("author", "")

        has_remote = bool(cat_id or page_url or remote_id)
        if not has_remote:
            self._apply_can_report_style()
            self.btn_report.setEnabled(True)
            return

        self.btn_report.setEnabled(False)
        self.btn_report.setText(tr("dependencies.checking_report_status"))
        self._apply_checking_style()

        payload = {
            "catalog_mod_id": cat_id,
            "source": source,
            "remote_id": remote_id,
            "page_url": page_url,
            "title": mod_title,
            "author": author,
            "missing_modules": self._missing_modules,
            "unnecessary_modules": self._unnecessary_modules,
        }
        self._check_worker = CheckReportStatusWorker(payload, parent=self)
        self._check_worker.status_ready.connect(self._on_status_ready)
        self._check_worker.start()

    def _on_status_ready(self, res: dict):
        self._status_result = res
        already_reported = res.get("already_reported", False)
        reported_at = res.get("reported_at")

        if already_reported:
            date_display = reported_at or tr("dependencies.previously")
            self.btn_report.setText(tr("dependencies.btn_already_reported", date=date_display))
            self._apply_already_reported_style()
            self.btn_report.setEnabled(False)
            self.btn_report.setToolTip(tr("dependencies.already_reported_tooltip"))
        else:
            self.btn_report.setText(tr("dependencies.btn_report_author"))
            self._apply_can_report_style()
            self.btn_report.setEnabled(True)
            self.btn_report.setToolTip(tr("dependencies.btn_report_tooltip"))

    def _on_clicked(self):
        if not self._status_result:
            return

        is_auth = self._status_result.get("is_authenticated", True)
        source = self._mod_data.get("source", "loverslab")
        if not is_auth:
            QMessageBox.warning(
                self,
                tr("dialogs.warning"),
                tr("dependencies.not_authenticated_warning", source=source.capitalize()),
            )
            return

        mod_title = self._mod_data.get("title", "")
        author = self._status_result.get("author") or self._mod_data.get("author", "")
        formatted_msg = self._status_result.get("formatted_message", "")
        cat_id = self._mod_data.get("id") or self._mod_data.get("catalog_mod_id")
        overrides = dict(self._mod_data.get("requirements_overrides", {}) or {})

        dlg = ReportPreviewDialog(
            mod_title=mod_title,
            author=author,
            missing_modules=self._missing_modules,
            unnecessary_modules=self._unnecessary_modules,
            requirements_overrides=overrides,
            source=source,
            page_url=self._mod_data.get("page_url", ""),
            remote_id=str(self._mod_data.get("remote_id", "")),
            catalog_mod_id=cat_id,
            initial_message=formatted_msg,
            parent=self.window(),
        )
        dlg.override_changed.connect(self.override_changed.emit)
        dlg.report_sent.connect(self._on_report_sent_success)
        dlg.exec()

    def _on_report_sent_success(self, reported_at: str):
        self.btn_report.setText(tr("dependencies.btn_already_reported_now"))
        self._apply_already_reported_style()
        self.btn_report.setEnabled(False)
        self.btn_report.setToolTip(tr("dependencies.already_reported_tooltip"))
        self.report_sent.emit(reported_at)

    def _apply_checking_style(self):
        self.btn_report.setStyleSheet("""
            QPushButton {
                background-color: #1e1b4b;
                color: #818cf8;
                border: 1px solid #4338ca;
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: 600;
                font-size: 11px;
            }
        """)

    def _apply_can_report_style(self):
        self.btn_report.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border: 1px solid #6366f1;
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #6366f1; }
        """)

    def _apply_already_reported_style(self):
        self.btn_report.setStyleSheet("""
            QPushButton {
                background-color: #141724;
                color: #64748b;
                border: 1px solid #232738;
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: 600;
                font-size: 11px;
            }
        """)

    def cleanup(self):
        if self._check_worker and self._check_worker.isRunning():
            self._check_worker.quit()
            self._check_worker.wait(200)
