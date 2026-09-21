"""
Unified DependencyCardWidget used across ModDetailView and DependenciesDialog.
Eliminates duplicated styling and layout code for requirements items.
"""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from src.ui.theme import Theme


class DependencyCardWidget(QFrame):
    """
    Renders a unified dependency card: prefix + title, status badge, and optional action button.
    """

    def __init__(
        self,
        title: str,
        badge_text: str,
        badge_variant: str = "neutral",
        prefix: str = "•",
        action_btn: Optional[QPushButton] = None,
        dashed: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setStyleSheet(Theme.card_frame_style(dashed=dashed))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        # Prefix + Title
        display_text = f"{prefix} {title}" if prefix else title
        self.lbl_title = QLabel(display_text)
        self.lbl_title.setStyleSheet("color: #f1f5f9; font-size: 11px; font-weight: 600;")
        layout.addWidget(self.lbl_title, stretch=1)

        # Status badge
        self.lbl_badge = QLabel(badge_text)
        self.lbl_badge.setStyleSheet(Theme.badge_style(variant=badge_variant))
        self.lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_badge)

        # Optional action button
        if action_btn:
            layout.addWidget(action_btn)
