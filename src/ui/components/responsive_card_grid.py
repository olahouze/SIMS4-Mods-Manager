from typing import List, Optional
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QLayoutItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent


class ResponsiveCardGrid(QWidget):
    """
    Reusable responsive grid layout for Mod cards.
    Automatically adapts column count (1 to 6+) based on available container width
    during resize events, preserving existing card widgets without costly recreations.
    """

    def __init__(
        self,
        min_card_width: int = 250,
        spacing: int = 14,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.min_card_width = max(120, min_card_width)
        self.grid_spacing = spacing
        self._cards: List[QWidget] = []
        self._current_columns = 4
        self._empty_label: Optional[QLabel] = None

        self._grid_layout = QGridLayout(self)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setSpacing(self.grid_spacing)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

    @property
    def cards(self) -> List[QWidget]:
        """Exécute l'opération cards.

        Returns:
            Résultat de l'opération cards.
        """
        return self._cards

    def calculate_columns(self, available_width: int) -> int:
        """Calculates optimal number of columns based on container width."""
        if available_width <= 0:
            return 1
        # Leave a safety margin of at least 14px to prevent vertical scrollbar trigger from causing horizontal overflow
        effective_w = max(0, available_width - 14)
        cols = (effective_w + self.grid_spacing) // (self.min_card_width + self.grid_spacing)
        return max(1, cols)

    def set_empty_message(self, message: str) -> None:
        """Displays a centered message when no cards are available."""
        self.clear()
        self._empty_label = QLabel(message)
        self._empty_label.setStyleSheet("font-size: 14px; color: #64748b; padding: 40px;")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grid_layout.addWidget(self._empty_label, 0, 0)

    def set_cards(self, cards: List[QWidget]) -> None:
        """Replaces current cards with a new collection and re-lays them out."""
        self.clear()
        self._cards = list(cards)

        available_w = self.width()
        if available_w > 50:
            self._current_columns = self.calculate_columns(available_w)
        self._re_layout()

    def add_card(self, card: QWidget) -> None:
        """Appends a single card to the grid."""
        if self._empty_label:
            self._empty_label.deleteLater()
            self._empty_label = None

        self._cards.append(card)
        idx = len(self._cards) - 1
        row = idx // self._current_columns
        col = idx % self._current_columns
        self._grid_layout.addWidget(card, row, col)

    def clear(self) -> None:
        """Removes and schedules deletion for all card widgets and empty labels."""
        while self._grid_layout.count():
            item: QLayoutItem = self._grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._cards.clear()
        self._empty_label = None

    def _re_layout(self) -> None:
        """Re-distributes card widgets across rows and columns using current column count."""
        # Detach without deleting widgets
        while self._grid_layout.count():
            self._grid_layout.takeAt(0)

        cols = max(1, self._current_columns)
        for idx, card in enumerate(self._cards):
            row = idx // cols
            col = idx % cols
            self._grid_layout.addWidget(card, row, col)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Dynamically updates grid layout if available width supports more/fewer columns."""
        super().resizeEvent(event)
        new_w = event.size().width()
        new_cols = self.calculate_columns(new_w)
        if new_cols != self._current_columns and self._cards:
            self._current_columns = new_cols
            self._re_layout()
