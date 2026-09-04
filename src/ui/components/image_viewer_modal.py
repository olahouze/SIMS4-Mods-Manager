from typing import List
from pathlib import Path
import hashlib
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QKeyEvent

from src.core.session_manager import SessionManager


class FullImageFetchWorker(QThread):
    loaded = Signal(str, str)  # url, local_path
    failed = Signal(str, str)

    def __init__(self, image_url: str, cache_dir: Path):
        super().__init__()
        self.image_url = image_url
        self.cache_dir = cache_dir

    def run(self):
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            url_hash = hashlib.md5(self.image_url.encode("utf-8")).hexdigest()
            ext = ".jpg"
            if ".png" in self.image_url.lower():
                ext = ".png"
            elif ".webp" in self.image_url.lower():
                ext = ".webp"
            cached_file = self.cache_dir / f"full_{url_hash}{ext}"

            if cached_file.exists() and cached_file.stat().st_size > 0:
                self.loaded.emit(self.image_url, str(cached_file))
                return

            session = SessionManager.get_http_session("loverslab")
            resp = session.get(self.image_url, timeout=20)
            if resp.status_code == 200 and len(resp.content) > 0:
                with open(cached_file, "wb") as f:
                    f.write(resp.content)
                self.loaded.emit(self.image_url, str(cached_file))
            else:
                self.failed.emit(self.image_url, f"Code HTTP {resp.status_code}")
        except Exception as e:
            self.failed.emit(self.image_url, str(e))


class ImageViewerModal(QDialog):
    """
    Full-size image viewer modal for mod screenshot galleries.
    Supports navigation between screenshots, smooth scaling, and keyboard shortcuts.
    """

    def __init__(self, images: List[str], current_index: int = 0, parent=None):
        super().__init__(parent)
        self.images = images or []
        self.current_index = max(0, min(current_index, len(self.images) - 1)) if self.images else 0
        self.cache_dir = Path.home() / ".sims4_mod_manager" / "cache" / "screenshots"
        self.fetch_worker = None

        self.setWindowTitle("Visionneuse de Captures d'écran")
        self.resize(1050, 750)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._init_ui()
        if self.images:
            self.counter_lbl.setText(f"Photo {self.current_index + 1} / {len(self.images)}")

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)

        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #0b0f19;
                border: 1px solid #1e293b;
                border-radius: 12px;
            }
        """)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(18, 14, 18, 18)
        c_layout.setSpacing(12)

        # Header: Counter and Close button
        header_layout = QHBoxLayout()
        self.counter_lbl = QLabel(f"Photo {self.current_index + 1} / {len(self.images)}")
        self.counter_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #94a3b8;")
        header_layout.addWidget(self.counter_lbl)

        header_layout.addStretch()

        close_btn = QPushButton("✕ Fermer")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedHeight(30)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: #ffffff;
                border-color: #ef4444;
            }
        """)
        close_btn.clicked.connect(self.accept)
        header_layout.addWidget(close_btn)

        c_layout.addLayout(header_layout)

        # Image Display Area
        self.image_lbl = QLabel("Chargement de l'image haute définition...")
        self.image_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_lbl.setStyleSheet("""
            QLabel {
                background-color: #050811;
                border: 1px solid #141b2d;
                border-radius: 8px;
                color: #64748b;
                font-size: 14px;
            }
        """)
        c_layout.addWidget(self.image_lbl, stretch=1)

        # Navigation Bar
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(12)

        self.prev_btn = QPushButton("◀ Précédente")
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setFixedHeight(36)
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 8px;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 18px;
            }
            QPushButton:hover { background-color: #334155; }
            QPushButton:disabled { background-color: #0f172a; color: #475569; border-color: #1e293b; }
        """)
        self.prev_btn.clicked.connect(self._on_prev)
        nav_layout.addWidget(self.prev_btn)

        nav_layout.addStretch()

        self.next_btn = QPushButton("Suivante ▶")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setFixedHeight(36)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 8px;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 18px;
            }
            QPushButton:hover { background-color: #334155; }
            QPushButton:disabled { background-color: #0f172a; color: #475569; border-color: #1e293b; }
        """)
        self.next_btn.clicked.connect(self._on_next)
        nav_layout.addWidget(self.next_btn)

        c_layout.addLayout(nav_layout)
        main_layout.addWidget(container)

    def _load_current_image(self):
        if not self.images:
            self.image_lbl.setText("Aucune image disponible.")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        total = len(self.images)
        self.counter_lbl.setText(f"Photo {self.current_index + 1} / {total}")
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < total - 1)

        url = self.images[self.current_index]

        # Check local cache first
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        ext = ".jpg"
        if ".png" in url.lower():
            ext = ".png"
        elif ".webp" in url.lower():
            ext = ".webp"
        cached_file = self.cache_dir / f"full_{url_hash}{ext}"

        if cached_file.exists() and cached_file.stat().st_size > 0:
            pix = QPixmap(str(cached_file))
            if not pix.isNull():
                self._display_pixmap(pix)
                return

        # Fetch in background
        self.image_lbl.setText("⏳ Chargement de l'image haute définition...")
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.fetch_worker.terminate()

        self.fetch_worker = FullImageFetchWorker(url, self.cache_dir)
        self.fetch_worker.loaded.connect(self._on_image_loaded)
        self.fetch_worker.failed.connect(self._on_image_failed)
        self.fetch_worker.start()

    def _on_image_loaded(self, url: str, path: str):
        if self.images and self.images[self.current_index] == url:
            pix = QPixmap(path)
            if not pix.isNull():
                self._display_pixmap(pix)
            else:
                self.image_lbl.setText("⚠️ Impossible de décoder l'image.")

    def _on_image_failed(self, url: str, err: str):
        if self.images and self.images[self.current_index] == url:
            self.image_lbl.setText(f"⚠️ Échec du chargement de l'image ({err})")

    def _display_pixmap(self, pix: QPixmap):
        avail_w = max(self.width() - 80, 400)
        avail_h = max(self.height() - 140, 300)
        scaled = pix.scaled(
            avail_w,
            avail_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_lbl.setPixmap(scaled)
        self.image_lbl.setText("")

    def _on_prev(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._load_current_image()

    def _on_next(self):
        if self.current_index < len(self.images) - 1:
            self.current_index += 1
            self._load_current_image()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Left:
            self._on_prev()
        elif event.key() == Qt.Key.Key_Right:
            self._on_next()
        elif event.key() == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._load_current_image()

    def closeEvent(self, event):
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.fetch_worker.terminate()
            self.fetch_worker.wait(500)
        super().closeEvent(event)

    def reject(self):
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.fetch_worker.terminate()
            self.fetch_worker.wait(500)
        super().reject()

    def accept(self):
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.fetch_worker.terminate()
            self.fetch_worker.wait(500)
        super().accept()
