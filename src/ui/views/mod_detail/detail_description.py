from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser
from src.ui.workers import DescriptionImageLoaderWorker
from src.utils.thread_utils import safe_stop_thread


class DetailDescriptionWidget(QWidget):
    """Component handling the rich HTML description view with asynchronous inline image loading."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.desc_img_worker: Optional[DescriptionImageLoaderWorker] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.desc_browser = QTextBrowser(self)
        self.desc_browser.setOpenExternalLinks(True)
        self.desc_browser.setMinimumHeight(450)
        self.desc_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #0b0e18;
                color: #e2e8f0;
                border: 1px solid #1a2235;
                border-radius: 12px;
                padding: 18px;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(self.desc_browser)

    def set_loading(self) -> None:
        """Resets the browser with a clean loading skeleton."""
        self.stop_worker()
        self.desc_browser.setHtml("""
            <div style='text-align: center; padding: 60px 20px; color: #64748b; font-family: sans-serif;'>
                <div style='font-size: 32px; margin-bottom: 12px;'>⏳</div>
                <div style='font-size: 15px; font-weight: 700; color: #94a3b8;'>Chargement des détails et de la description...</div>
                <div style='font-size: 12px; margin-top: 6px; color: #475569;'>Inspection des prérequis et des galeries d'images</div>
            </div>
        """)

    def set_content(self, raw_html: str) -> None:
        """Sets HTML content and triggers background inline image downloading."""
        self.stop_worker()
        if not raw_html:
            raw_html = "<p style='color:#94a3b8;'>Aucune description disponible pour ce mod.</p>"
        self.desc_browser.setHtml(raw_html)

        self.desc_img_worker = DescriptionImageLoaderWorker(raw_html)
        self.desc_img_worker.images_updated.connect(self._on_images_updated)
        self.desc_img_worker.start()

    def set_error(self, err_msg: str) -> None:
        """Displays error message when details failed to fetch."""
        self.stop_worker()
        self.desc_browser.setHtml(
            f"<p style='color:#94a3b8;'>Impossible de charger la description en ligne ({err_msg}).</p>"
        )

    def _on_images_updated(self, updated_html: str) -> None:
        v_bar = self.desc_browser.verticalScrollBar()
        scroll_pos = v_bar.value()
        self.desc_browser.setHtml(updated_html)
        v_bar.setValue(scroll_pos)

    def stop_worker(self) -> None:
        if self.desc_img_worker:
            safe_stop_thread(self.desc_img_worker)
            self.desc_img_worker = None
