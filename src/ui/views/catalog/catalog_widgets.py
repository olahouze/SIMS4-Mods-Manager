"""
Reusable helper widgets for CatalogView (Sync banner and pagination bar).
"""

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QProgressBar,
)
from PySide6.QtCore import Qt, Signal

from src.i18n import tr


class CatalogSyncBannerWidget(QFrame):
    """Non-blocking banner showing real-time background sync progress."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SyncBanner")
        self.setVisible(False)
        self.setStyleSheet("""
            QFrame#SyncBanner {
                background-color: #1a1d30;
                border: 1px solid #4f46e5;
                border-radius: 8px;
                padding: 10px 14px;
            }
        """)
        b_layout = QHBoxLayout(self)
        b_layout.setContentsMargins(0, 0, 0, 0)
        b_layout.setSpacing(12)

        self.sync_banner_lbl = QLabel(tr("catalog.sync_running"))
        self.sync_banner_lbl.setStyleSheet("font-size: 12px; color: #cbd5e1; font-weight: 600;")
        b_layout.addWidget(self.sync_banner_lbl, stretch=2)

        self.sync_bar = QProgressBar()
        self.sync_bar.setFixedHeight(12)
        self.sync_bar.setRange(0, 100)
        self.sync_bar.setValue(0)
        self.sync_bar.setTextVisible(False)
        self.sync_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0f111a;
                border-radius: 6px;
                border: 1px solid #282e44;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
                border-radius: 5px;
            }
        """)
        b_layout.addWidget(self.sync_bar, stretch=3)

    def set_running(self, message: str, percent: int, is_paused: bool = False):
        """Exécute l'opération set running.

        Args:
            message: Paramètre message.
            percent: Paramètre percent.
            is_paused: Paramètre is_paused.
        """
        self.setVisible(True)
        prefix = "⏸️" if is_paused else "🔄"
        self.sync_banner_lbl.setText(f"{prefix} {message}")
        self.sync_bar.setValue(percent)

    def set_error(self, err_msg: str):
        """Exécute l'opération set error.

        Args:
            err_msg: Paramètre err_msg.
        """
        self.setVisible(True)
        self.sync_banner_lbl.setText(f"⚠️ Erreur scraping : {err_msg}")

    def set_idle(self):
        """Exécute l'opération set idle."""
        self.setVisible(False)


class CatalogPaginationBar(QWidget):
    """Pagination navigation controls (Previous, Next, and Page count label)."""

    prev_requested = Signal()
    next_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.btn_prev = QPushButton(tr("catalog.pagination_prev"))
        self.btn_prev.setProperty("class", "SecondaryBtn")
        self.btn_prev.setEnabled(False)
        self.btn_prev.clicked.connect(self.prev_requested.emit)
        layout.addWidget(self.btn_prev)

        self.lbl_page_info = QLabel(tr("catalog.page_info", current=1, total=1, total_items=0))
        self.lbl_page_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_page_info.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 500;")
        layout.addWidget(self.lbl_page_info)

        self.btn_next = QPushButton(tr("catalog.pagination_next"))
        self.btn_next.setProperty("class", "SecondaryBtn")
        self.btn_next.setEnabled(False)
        self.btn_next.clicked.connect(self.next_requested.emit)
        layout.addWidget(self.btn_next)

    def update_pagination(self, current_page: int, total_pages: int, total_items: int):
        """Exécute l'opération update pagination.

        Args:
            current_page: Paramètre current_page.
            total_pages: Paramètre total_pages.
            total_items: Paramètre total_items.
        """
        self.btn_prev.setEnabled(current_page > 1)
        self.btn_next.setEnabled(current_page < total_pages)
        self.lbl_page_info.setText(
            tr("catalog.page_info", current=current_page, total=total_pages, total_items=total_items)
        )

    def retranslate_ui(self):
        """Exécute l'opération retranslate ui."""
        self.btn_prev.setText(tr("catalog.pagination_prev"))
        self.btn_next.setText(tr("catalog.pagination_next"))
