"""
Individual gallery thumbnail item widget for ModDetailView.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QCursor
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel

from src.ui.theme import Theme


class GalleryItemWidget(QFrame):
    clicked = Signal(int)

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setFixedSize(170, 110)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet(Theme.card_frame_style(interactive=True, radius=8, padding="0px"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.img_lbl = QLabel()
        self.img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_lbl.setStyleSheet("background-color: #0b0e17; border-radius: 8px; color: #475569; font-size: 11px;")
        self.img_lbl.setText("Chargement...")
        layout.addWidget(self.img_lbl)

    def set_pixmap(self, pix: QPixmap):
        self.img_lbl.setText("")
        self.img_lbl.setPixmap(pix)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)
        super().mousePressEvent(event)
