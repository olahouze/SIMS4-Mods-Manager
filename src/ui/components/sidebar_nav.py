"""
Sidebar navigation widget with branding, navigation buttons, game detection status, and quick launch button.
"""

from typing import List
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Signal

from src.i18n import tr


class SidebarNavWidget(QFrame):
    """Left sidebar component managing main view switching and game launcher status."""

    page_requested = Signal(int)
    launch_game_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(240)
        self.nav_buttons: List[QPushButton] = []
        self._init_ui()

    def _init_ui(self):
        sidebar_layout = QVBoxLayout(self)
        sidebar_layout.setContentsMargins(16, 20, 16, 20)
        sidebar_layout.setSpacing(8)

        # Brand / Logo Header
        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(2)

        app_title = QLabel("SIMS 4")
        app_title.setObjectName("AppTitle")
        brand_layout.addWidget(app_title)

        app_subtitle = QLabel("MODS MANAGER")
        app_subtitle.setObjectName("AppSubtitle")
        brand_layout.addWidget(app_subtitle)

        sidebar_layout.addLayout(brand_layout)
        sidebar_layout.addSpacing(20)

        # Navigation Buttons
        self.btn_accounts = self._create_nav_button(tr("nav.accounts"), 0)
        self.btn_catalog = self._create_nav_button(tr("nav.catalog"), 1)
        self.btn_installed = self._create_nav_button(tr("nav.installed"), 2)
        self.btn_downloads = self._create_nav_button(tr("nav.downloads"), 3)
        self.btn_updates = self._create_nav_button(tr("nav.updates"), 4)
        self.btn_logs = self._create_nav_button(tr("nav.logs"), 5)
        self.btn_settings = self._create_nav_button(tr("nav.settings"), 6)

        sidebar_layout.addWidget(self.btn_accounts)
        sidebar_layout.addWidget(self.btn_catalog)
        sidebar_layout.addWidget(self.btn_installed)
        sidebar_layout.addWidget(self.btn_downloads)
        sidebar_layout.addWidget(self.btn_updates)
        sidebar_layout.addWidget(self.btn_logs)
        sidebar_layout.addWidget(self.btn_settings)

        sidebar_layout.addStretch()

        # Quick Launch Game in Sidebar Footer
        footer_layout = QVBoxLayout()
        footer_layout.setSpacing(6)

        self.game_status = QLabel(tr("nav.game_checking"))
        self.game_status.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 600; padding: 4px 0;")
        footer_layout.addWidget(self.game_status)

        self.play_btn = QPushButton(tr("nav.launch_game"))
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                border-radius: 8px;
                padding: 10px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.play_btn.clicked.connect(self.launch_game_requested.emit)
        footer_layout.addWidget(self.play_btn)

        sidebar_layout.addLayout(footer_layout)

    def _create_nav_button(self, text: str, page_index: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("class", "NavButton")
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self.page_requested.emit(page_index))
        self.nav_buttons.append(btn)
        return btn

    def set_active_page(self, index: int):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def update_game_status(self, success: bool, mods_detected: bool):
        if success:
            if mods_detected:
                self.game_status.setText(tr("nav.game_detected"))
                self.game_status.setStyleSheet("font-size: 11px; color: #34d399; font-weight: 600; padding: 4px 0;")
            else:
                self.game_status.setText(tr("nav.game_not_detected"))
                self.game_status.setStyleSheet("font-size: 11px; color: #f87171; font-weight: 600; padding: 4px 0;")
        else:
            self.game_status.setText(tr("nav.game_api_error"))
            self.game_status.setStyleSheet("font-size: 11px; color: #f87171; font-weight: 600; padding: 4px 0;")

    def update_badge_count(self, count: int):
        if count > 0:
            self.btn_updates.setText(tr("nav.updates_with_count", count=count))
        else:
            self.btn_updates.setText(tr("nav.updates"))

    def update_downloads_badge(self, count: int):
        if count > 0:
            self.btn_downloads.setText(tr("nav.downloads_with_count", count=count))
        else:
            self.btn_downloads.setText(tr("nav.downloads"))

    def retranslate_ui(self):
        self.btn_accounts.setText(tr("nav.accounts"))
        self.btn_catalog.setText(tr("nav.catalog"))
        self.btn_installed.setText(tr("nav.installed"))
        self.btn_downloads.setText(tr("nav.downloads"))
        self.btn_updates.setText(tr("nav.updates"))
        self.btn_logs.setText(tr("nav.logs"))
        self.btn_settings.setText(tr("nav.settings"))
        self.play_btn.setText(tr("nav.launch_game"))
