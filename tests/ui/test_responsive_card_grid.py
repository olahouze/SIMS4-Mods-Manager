from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QResizeEvent
from PySide6.QtCore import QSize

from src.ui.components.responsive_card_grid import ResponsiveCardGrid


def test_responsive_card_grid_column_calculation(qapp):
    grid = ResponsiveCardGrid(min_card_width=250, spacing=14)

    # 1 column for narrow widths
    assert grid.calculate_columns(200) == 1

    # (550 + 14) // (250 + 14) = 564 // 264 = 2 columns
    assert grid.calculate_columns(550) == 2

    # (1100 + 14) // 264 = 1114 // 264 = 4 columns
    assert grid.calculate_columns(1100) == 4

    # (1600 + 14) // 264 = 1614 // 264 = 6 columns
    assert grid.calculate_columns(1600) == 6


def test_responsive_card_grid_cards_lifecycle(qapp):
    grid = ResponsiveCardGrid(min_card_width=250, spacing=14)

    # Empty message
    grid.set_empty_message("Aucun mod trouvé")
    assert grid._grid_layout.count() == 1

    # Populate cards
    cards = [QLabel(f"Card {i}") for i in range(7)]
    grid.set_cards(cards)
    assert len(grid.cards) == 7
    assert grid._grid_layout.count() == 7

    # Add single card
    extra_card = QLabel("Extra Card")
    grid.add_card(extra_card)
    assert len(grid.cards) == 8
    assert grid._grid_layout.count() == 8

    # Clear
    grid.clear()
    assert len(grid.cards) == 0
    assert grid._grid_layout.count() == 0


def test_responsive_card_grid_resize_preserves_widgets(qapp):
    grid = ResponsiveCardGrid(min_card_width=250, spacing=14)
    cards = [QLabel(f"Card {i}") for i in range(6)]
    grid.set_cards(cards)

    original_widgets = list(grid.cards)

    # Simulate resize from narrow (1 col) to wide (4 cols)
    resize_event = QResizeEvent(QSize(1200, 800), QSize(300, 800))
    grid.resizeEvent(resize_event)

    # Cards must still be present and not destroyed
    assert len(grid.cards) == 6
    assert grid.cards == original_widgets
    assert grid._current_columns >= 4
