"""
DetailHeaderWidget: Top metadata banner, tags, and action buttons for ModDetailView.
"""

from typing import Any, Dict
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)

from src.ui.theme import Theme
from src.i18n import tr


class DetailHeaderWidget(QWidget):
    back_requested = Signal()
    install_requested = Signal()
    uninstall_requested = Signal()
    open_folder_requested = Signal()
    open_web_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_installed: bool = False
        self.has_update: bool = False
        self.origin_name: str = "Catalogue"
        self.origin_index: int = 1
        self._mod_data: Dict[str, Any] = {}
        self._thumb_label = QLabel(self)
        self._thumb_label.setVisible(False)
        self._installed_badge = QLabel(self)
        self._installed_badge.setVisible(False)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 8)
        main_layout.setSpacing(12)

        # Top row: Back button + Title + Action buttons
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.btn_back = QPushButton(tr("mod_detail.back"))
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.setStyleSheet(Theme.action_button_style(variant="subtle", padding="6px 14px"))
        self.btn_back.clicked.connect(self.back_requested.emit)
        top_row.addWidget(self.btn_back)

        # Title & Author block
        title_block = QVBoxLayout()
        title_block.setSpacing(2)

        self.lbl_title = QLabel("Titre du Mod")
        self.lbl_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #f8fafc;")
        self.lbl_title.setWordWrap(True)
        title_block.addWidget(self.lbl_title)

        author_row = QHBoxLayout()
        author_row.setSpacing(8)

        self.lbl_author = QLabel("par Auteur")
        self.lbl_author.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 500;")
        author_row.addWidget(self.lbl_author)

        self.badge_access = QLabel("Accès Direct")
        self.badge_access.setStyleSheet(Theme.badge_style(variant="info", padding="2px 8px"))
        author_row.addWidget(self.badge_access)
        author_row.addStretch()

        title_block.addLayout(author_row)
        top_row.addLayout(title_block, stretch=1)

        # Action buttons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        self.btn_open_folder = QPushButton(tr("mod_detail.btn_open_folder"))
        self.btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_folder.setStyleSheet(Theme.action_button_style(variant="subtle", padding="8px 14px"))
        self.btn_open_folder.clicked.connect(self.open_folder_requested.emit)
        self.btn_open_folder.setVisible(False)
        actions_layout.addWidget(self.btn_open_folder)

        self.btn_open_web = QPushButton("🌐 Page Officielle")
        self.btn_open_web.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_web.setStyleSheet(Theme.action_button_style(variant="subtle", padding="8px 14px"))
        self.btn_open_web.clicked.connect(self.open_web_requested.emit)
        actions_layout.addWidget(self.btn_open_web)

        self.btn_install = QPushButton(tr("mod_detail.btn_install"))
        self.btn_install.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_install.setStyleSheet(Theme.action_button_style(variant="primary", font_size=13, padding="8px 20px"))
        self.btn_install.clicked.connect(self._on_install_btn_clicked)
        actions_layout.addWidget(self.btn_install)

        top_row.addLayout(actions_layout)
        main_layout.addLayout(top_row)

        # Metadata banner: Version, Dates, Tags
        self.meta_frame = QFrame()
        self.meta_frame.setStyleSheet(Theme.card_frame_style(bg="#111422", border="#1e253b", padding="6px 12px"))
        meta_layout = QHBoxLayout(self.meta_frame)
        meta_layout.setContentsMargins(4, 2, 4, 2)
        meta_layout.setSpacing(16)

        self.lbl_version = QLabel("Version: -")
        self.lbl_version.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: 600;")
        meta_layout.addWidget(self.lbl_version)

        self.lbl_updated = QLabel("Mis à jour: -")
        self.lbl_updated.setStyleSheet("color: #94a3b8; font-size: 11px;")
        meta_layout.addWidget(self.lbl_updated)

        self.lbl_tags = QLabel("")
        self.lbl_tags.setStyleSheet("color: #818cf8; font-size: 11px;")
        self.lbl_tags.setWordWrap(True)
        meta_layout.addWidget(self.lbl_tags, stretch=1)

        main_layout.addWidget(self.meta_frame)

    def _on_install_btn_clicked(self):
        if self.is_installed and not self.has_update:
            self.uninstall_requested.emit()
        else:
            self.install_requested.emit()

    # Compatibility properties
    @property
    def back_btn(self):
        return self.btn_back

    @property
    def install_btn(self):
        return self.btn_install

    @property
    def open_folder_btn(self):
        return self.btn_open_folder

    @property
    def web_btn(self):
        return self.btn_open_web

    @property
    def title_lbl(self):
        return self.lbl_title

    @property
    def thumb_label(self):
        return self._thumb_label

    @property
    def meta_author(self):
        return self.lbl_author

    @property
    def meta_date(self):
        return self.lbl_updated

    @property
    def meta_tags(self):
        return self.lbl_tags

    @property
    def installed_badge(self):
        return self._installed_badge

    @property
    def source_badge(self):
        return self.badge_access

    def update_mod_info(self, mod_data: dict, origin_name: str = "Catalogue", origin_index: int = 1):
        self._mod_data = mod_data
        self.origin_name = origin_name
        self.origin_index = origin_index
        self.btn_back.setText(tr("mod_detail.back_to", origin=origin_name))

        title = mod_data.get("title", tr("mod_detail.title_default"))
        self.lbl_title.setText(title)

        author = mod_data.get("author") or tr("common.unknown")
        self.lbl_author.setText(tr("mod_detail.meta_author", author=author))

        date_val = mod_data.get("updated_date") or mod_data.get("installed_date") or ""
        date_str = str(date_val)[:10] if date_val else tr("mod_detail.date_unknown")
        self.lbl_updated.setText(tr("mod_detail.meta_date", date=date_str))

        tags = mod_data.get("tags") or []
        tags_str = ", ".join(tags) if tags else tr("mod_detail.no_tags")
        self.lbl_tags.setText(tr("mod_detail.meta_tags", tags=tags_str))

        source = mod_data.get("source", "loverslab")
        self.badge_access.setText(source.capitalize())

        self.is_installed = bool(mod_data.get("is_installed", False) or mod_data.get("installed_id"))
        self.has_update = bool(mod_data.get("has_update", False))

        if self.is_installed:
            self._installed_badge.setText(tr("catalog.installed_badge"))
            self.btn_open_folder.setVisible(True)
            if self.has_update:
                self.btn_install.setText(tr("mod_detail.btn_update"))
                self.btn_install.setStyleSheet(Theme.action_button_style(variant="warning", padding="8px 20px"))
            else:
                self.btn_install.setText(tr("catalog.btn_already_installed"))
                self.btn_install.setStyleSheet(Theme.action_button_style(variant="subtle", padding="8px 20px"))
        else:
            self._installed_badge.setText("Non installé")
            self.btn_open_folder.setVisible(False)
            self.btn_install.setText("📥 Installer le mod")
            self.btn_install.setStyleSheet(Theme.action_button_style(variant="primary", padding="8px 20px"))

    def retranslate_ui(self):
        self.btn_back.setText(tr("mod_detail.back_to", origin=self.origin_name))
        self.btn_open_folder.setText(tr("mod_detail.btn_open_folder"))
        self.btn_open_web.setText(tr("mod_detail.btn_official_page"))
        if self._mod_data:
            self.update_mod_info(self._mod_data, self.origin_name, self.origin_index)
