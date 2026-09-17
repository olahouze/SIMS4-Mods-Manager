import threading
from typing import Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QApplication,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from src.services.browser_updater_service import BrowserUpdaterService
from src.i18n import tr
from src.utils.logger import logger
from src.utils.thread_utils import BaseWorker, safe_stop_thread


class BrowserInstallWorker(BaseWorker):
    """Worker task running the Playwright Chromium installation stream."""

    progress_updated = Signal(int, str)
    install_finished = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancel_event = threading.Event()

    def cancel(self):
        super().cancel()
        self._cancel_event.set()

    def run(self):
        self._is_running = True
        try:
            def _on_progress(pct: int, msg: str):
                if not self._is_cancelled:
                    self.progress_updated.emit(pct, msg)

            success, msg = BrowserUpdaterService.install_chromium_stream(
                progress_callback=_on_progress,
                cancel_event=self._cancel_event,
            )
            if not self._is_cancelled:
                self.install_finished.emit(success, msg)
        finally:
            self._is_running = False


class BrowserDownloadDialog(QDialog):
    """
    Modal progress dialog for downloading / updating Playwright Chromium.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("browser.dialog_title"))
        self.setMinimumWidth(480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setModal(True)

        self.success = False
        self.worker: Optional[BrowserInstallWorker] = None

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0d111d;
                color: #f8fafc;
                border-radius: 10px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header Title
        title_lbl = QLabel(tr("browser.dialog_header"))
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #f8fafc;")
        layout.addWidget(title_lbl)

        # Description
        desc_lbl = QLabel(tr("browser.dialog_desc"))
        desc_lbl.setStyleSheet("font-size: 12px; color: #94a3b8; line-height: 1.4;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # Status Label
        self.status_lbl = QLabel(tr("browser.starting_download"))
        self.status_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #a5b4fc;")
        self.status_lbl.setWordWrap(True)
        layout.addWidget(self.status_lbl)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e253b;
                border: 1px solid #334155;
                border-radius: 6px;
                height: 18px;
                text-align: center;
                color: #ffffff;
                font-weight: 700;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #818cf8);
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Action Buttons (Cancel)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton(tr("dialogs.cancel"))
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e253b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #28314d;
                color: #ffffff;
            }
        """)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def start_install(self):
        self.worker = BrowserInstallWorker(self)
        self.worker.progress_updated.connect(self._on_progress_updated)
        self.worker.install_finished.connect(self._on_install_finished)
        self.worker.start()

    def _on_progress_updated(self, percent: int, message: str):
        self.progress_bar.setValue(percent)
        self.status_lbl.setText(message)

    def _on_install_finished(self, success: bool, message: str):
        self.success = success
        if success:
            self.progress_bar.setValue(100)
            self.status_lbl.setText(tr("browser.install_success"))
            self.accept()
        else:
            self.status_lbl.setText(f"{tr('browser.install_error')}: {message}")
            QMessageBox.warning(
                self,
                tr("dialogs.warning"),
                f"{tr('browser.install_error')}\n\n{message}",
            )
            self.reject()

    def _on_cancel_clicked(self):
        if self.worker and self.worker.isRunning():
            self.status_lbl.setText(tr("browser.cancelling"))
            self.cancel_btn.setEnabled(False)
            self.worker.cancel()
        else:
            self.reject()

    def closeEvent(self, event):
        if self.worker:
            safe_stop_thread(self.worker)
            self.worker = None
        super().closeEvent(event)

    @classmethod
    def ensure_browser_ready(cls, parent=None) -> bool:
        """
        Just-in-time check. If Chromium is already ready, returns True immediately.
        Otherwise, displays the download dialog and returns True once installed, False on cancel/error.
        """
        if BrowserUpdaterService.is_chromium_ready():
            return True

        # Check if we are running in a GUI application
        app = QApplication.instance()
        if not app:
            logger.warning("Pas d'instance QApplication disponible pour afficher le dialogue de téléchargement.")
            return False

        dialog = cls(parent=parent)
        dialog.start_install()
        result = dialog.exec()
        return result == QDialog.Accepted and dialog.success
