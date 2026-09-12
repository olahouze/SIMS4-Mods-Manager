from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, Signal, QObject, QRunnable, QThreadPool

from src.core.config import AppConfig
from src.ui.components.image_cache import ImageCache
from src.api.client import get_api_client
from src.utils.logger import logger


class ImageLoadSignals(QObject):
    loaded = Signal(str, str)  # remote_id, local_path


class ImageDownloadTask(QRunnable):
    """Asynchronous background worker fetching remote thumbnails via API."""

    def __init__(self, source: str, remote_id: str, url: str, dest_path: Path, signals: ImageLoadSignals):
        super().__init__()
        self.source = source
        self.remote_id = remote_id
        self.url = url
        self.dest_path = dest_path
        self.signals = signals

    def run(self):
        try:
            api_client = get_api_client()
            resp = api_client.client.get(
                "/api/catalog/thumbnail",
                params={"source": self.source, "remote_id": self.remote_id, "url": self.url},
                timeout=20.0,
            )
            if resp.status_code == 200 and len(resp.content) > 100:
                self.dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.dest_path, "wb") as f:
                    f.write(resp.content)
                self.signals.loaded.emit(self.remote_id, str(self.dest_path))
        except Exception as e:
            logger.debug(f"Thumbnail download failed via API for {self.url}: {e}")


class BaseModCard(QFrame):
    """
    Common base class for ModCard and InstalledCard.
    Encapsulates thumbnail caching, asynchronous image downloading, and card framing.
    """

    details_requested = Signal(dict)

    def __init__(self, mod_data: dict, parent=None):
        super().__init__(parent)
        self.mod_data = mod_data
        self.thumb_label: Optional[QLabel] = None
        self.thumb_width = 271
        self.thumb_height = 145
        self.signals = ImageLoadSignals()
        self.signals.loaded.connect(self._on_image_loaded)

    def _create_thumbnail_container(self, height: int = 145) -> QLabel:
        """Creates standard thumbnail preview label with dark modern backdrop."""
        label = QLabel()
        label.setFixedHeight(height)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("""
            background-color: #0b0d17;
            border-radius: 10px;
            border: 1px solid #1a1e32;
            color: #64748b;
            font-size: 28px;
        """)
        label.setText("🎮")
        self.thumb_label = label
        self.thumb_height = height
        return label

    def _load_thumbnail_async(self):
        """Checks memory/disk cache or dispatches async download task."""
        thumb_url = self.mod_data.get("thumbnail_url", "")
        if not thumb_url:
            return

        scaled_pix = ImageCache.get_or_scale(thumb_url, self.thumb_width, self.thumb_height)
        if scaled_pix:
            if self.thumb_label:
                self.thumb_label.setPixmap(scaled_pix)
                self.thumb_label.setText("")
            return

        source = self.mod_data.get("source", "loverslab")
        remote_id = str(self.mod_data.get("remote_id", "unknown"))
        cache_name = f"thumb_{source}_{remote_id}.jpg"
        cache_path = AppConfig.get_thumbnails_cache_dir() / cache_name

        if cache_path.exists() and cache_path.stat().st_size > 100:
            self._display_image(str(cache_path))
        else:
            task = ImageDownloadTask(source, remote_id, thumb_url, cache_path, self.signals)
            QThreadPool.globalInstance().start(task)

    def _on_image_loaded(self, remote_id: str, local_path: str):
        """Callback invoked when ImageDownloadTask successfully downloads the image."""
        if str(self.mod_data.get("remote_id")) == remote_id:
            self._display_image(local_path)

    def _display_image(self, image_path: str):
        """Displays pixmap on thumb_label and saves both raw and pre-scaled versions to memory cache."""
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            thumb_url = self.mod_data.get("thumbnail_url", "")
            scaled = pixmap.scaled(
                self.thumb_width,
                self.thumb_height,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            if thumb_url:
                ImageCache.set(thumb_url, pixmap)
                ImageCache.set_scaled(thumb_url, self.thumb_width, self.thumb_height, scaled)
            if self.thumb_label:
                self.thumb_label.setPixmap(scaled)
                self.thumb_label.setText("")
