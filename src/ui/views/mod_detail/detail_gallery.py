"""
DetailGalleryWidget: Horizontal scrollable strip of screenshots thumbnails
with batch background loading and fullscreen viewer integration.
"""

from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
)

from src.core.config import AppConfig
from src.ui.views.mod_detail.gallery_item import GalleryItemWidget
from src.ui.workers.detail_workers import GalleryBatchWorker
from src.utils.thread_utils import safe_stop_thread
from src.i18n import tr


class DetailGalleryWidget(QWidget):
    image_clicked = Signal(int, list)  # (index, all_urls)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.screenshots: List[str] = []
        self._gallery_items: List[GalleryItemWidget] = []
        self._batch_worker: Optional[GalleryBatchWorker] = None
        self._current_load_id: int = 0
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(6)

        self.lbl_title = QLabel("📸 " + tr("mod_detail.gallery_title"))
        self.lbl_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #cbd5e1;")
        layout.addWidget(self.lbl_title)

        self.scroll_area = QScrollArea()
        self.scroll_area.setFixedHeight(126)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.strip_container = QWidget()
        self.strip_container.setStyleSheet("background: transparent;")
        self.strip_layout = QHBoxLayout(self.strip_container)
        self.strip_layout.setContentsMargins(0, 0, 0, 0)
        self.strip_layout.setSpacing(8)
        self.strip_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.scroll_area.setWidget(self.strip_container)
        layout.addWidget(self.scroll_area)
        self.setVisible(False)

    def render_gallery(self, screenshots: List[str], load_id: int = 0):
        self.cleanup()
        self.screenshots = list(screenshots or [])
        self._current_load_id = load_id

        if not self.screenshots:
            self.setVisible(False)
            return

        self.setVisible(True)
        self._gallery_items.clear()

        for idx in range(len(self.screenshots)):
            item = GalleryItemWidget(idx, self.strip_container)
            item.clicked.connect(self._on_item_clicked)
            self.strip_layout.addWidget(item)
            self._gallery_items.append(item)

        cache_dir = AppConfig.get_cache_dir() / "gallery_thumbs"
        self._batch_worker = GalleryBatchWorker(self.screenshots, cache_dir, load_id=load_id)
        self._batch_worker.thumb_ready.connect(self._on_thumb_ready)
        self._batch_worker.start()

    def _on_thumb_ready(self, idx: int, pix: QPixmap):
        if 0 <= idx < len(self._gallery_items):
            self._gallery_items[idx].set_pixmap(pix)

    def _on_item_clicked(self, index: int):
        self.image_clicked.emit(index, self.screenshots)

    def cleanup(self):
        if self._batch_worker:
            safe_stop_thread(self._batch_worker)
            self._batch_worker = None

        while self.strip_layout.count():
            item = self.strip_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._gallery_items.clear()

    def clear_gallery(self):
        self.cleanup()
        self.setVisible(False)
