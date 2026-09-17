"""
UpdatesToolbarBuilder: Builds the header stats bar and the selection/search toolbar for UpdatesView.
"""
from PySide6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
)
from src.i18n import tr


def build_updates_header(view) -> QHBoxLayout:
    """Creates the top header bar with titles and primary action buttons."""
    header_layout = QHBoxLayout()
    header_layout.setSpacing(12)

    header_title_layout = QVBoxLayout()
    header_title_layout.setSpacing(4)

    view.main_title = QLabel(tr("updates.title"))
    view.main_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #f8fafc;")
    header_title_layout.addWidget(view.main_title)

    view.counter_label = QLabel(tr("updates.searching"))
    view.counter_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #94a3b8;")
    header_title_layout.addWidget(view.counter_label)

    header_layout.addLayout(header_title_layout)
    header_layout.addStretch()

    view.refresh_btn = QPushButton(tr("updates.refresh_btn"))
    view.refresh_btn.setStyleSheet("""
        QPushButton {
            background-color: #1e2238;
            color: #e2e8f0;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 600;
            font-size: 13px;
            min-height: 22px;
        }
        QPushButton:hover { background-color: #2a2f4c; border-color: #6366f1; }
    """)
    view.refresh_btn.clicked.connect(view.refresh_updates)
    header_layout.addWidget(view.refresh_btn)

    view.update_selected_btn = QPushButton(tr("updates.update_selected_btn", count=0))
    view.update_selected_btn.setEnabled(False)
    view.update_selected_btn.setStyleSheet("""
        QPushButton {
            background-color: #4f46e5;
            color: #ffffff;
            border-radius: 6px;
            padding: 8px 18px;
            font-weight: 700;
            font-size: 13px;
            min-height: 22px;
        }
        QPushButton:hover { background-color: #6366f1; }
        QPushButton:disabled {
            background-color: #1e2238;
            color: #475569;
            border: 1px solid #282e44;
        }
    """)
    view.update_selected_btn.clicked.connect(view.update_selected_mods)
    header_layout.addWidget(view.update_selected_btn)

    view.update_all_btn = QPushButton(tr("updates.update_all_btn"))
    view.update_all_btn.setEnabled(False)
    view.update_all_btn.setStyleSheet("""
        QPushButton {
            background-color: #eab308;
            color: #000000;
            border-radius: 6px;
            padding: 8px 18px;
            font-weight: 700;
            font-size: 13px;
            min-height: 22px;
        }
        QPushButton:hover { background-color: #facc15; }
        QPushButton:disabled {
            background-color: #1e2238;
            color: #475569;
            border: 1px solid #282e44;
        }
    """)
    view.update_all_btn.clicked.connect(view.update_all_mods)
    header_layout.addWidget(view.update_all_btn)

    return header_layout


def build_updates_toolbar(view) -> QHBoxLayout:
    """Creates the selection toolbar and search filter input."""
    toolbar_layout = QHBoxLayout()
    toolbar_layout.setSpacing(10)

    view.select_updates_btn = QPushButton(tr("updates.select_updates_btn"))
    view.select_updates_btn.setToolTip(tr("updates.select_updates_tip"))
    view.select_updates_btn.setStyleSheet("""
        QPushButton {
            background-color: #1e2238;
            color: #38bdf8;
            border: 1px solid #0284c7;
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 600;
        }
        QPushButton:hover { background-color: #0369a1; color: #ffffff; }
    """)
    view.select_updates_btn.clicked.connect(view.select_updates_only)
    toolbar_layout.addWidget(view.select_updates_btn)

    view.select_all_btn = QPushButton(tr("updates.select_all_btn"))
    view.select_all_btn.setStyleSheet("""
        QPushButton {
            background-color: #1e2238;
            color: #cbd5e1;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 12px;
        }
        QPushButton:hover { background-color: #2a2f4c; color: #ffffff; }
    """)
    view.select_all_btn.clicked.connect(view.select_all)
    toolbar_layout.addWidget(view.select_all_btn)

    view.deselect_all_btn = QPushButton(tr("updates.deselect_all_btn"))
    view.deselect_all_btn.setStyleSheet("""
        QPushButton {
            background-color: #1e2238;
            color: #94a3b8;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 12px;
        }
        QPushButton:hover { background-color: #2a2f4c; color: #cbd5e1; }
    """)
    view.deselect_all_btn.clicked.connect(view.deselect_all)
    toolbar_layout.addWidget(view.deselect_all_btn)

    toolbar_layout.addStretch()

    # Search Bar
    view.search_input = QLineEdit()
    view.search_input.setPlaceholderText(tr("updates.search_placeholder"))
    view.search_input.setFixedWidth(260)
    view.search_input.setStyleSheet("""
        QLineEdit {
            background-color: #131728;
            color: #f8fafc;
            border: 1px solid #282e44;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 12px;
        }
        QLineEdit:focus {
            border: 1px solid #4f46e5;
        }
    """)
    view.search_input.textChanged.connect(view._apply_filter)
    toolbar_layout.addWidget(view.search_input)

    return toolbar_layout
