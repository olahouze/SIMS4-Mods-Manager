from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from src.api.client import get_api_client
from src.ui.components.installed_card import InstalledCard
from src.ui.components.responsive_card_grid import ResponsiveCardGrid
from src.ui.utils.dialog_helper import DialogHelper
from src.i18n import tr
from src.utils.logger import logger


class InstalledView(QWidget):
    """
    Modern grid view managing installed Sims 4 mods.
    Displays rich cards with cover previews, metadata, direct folder access, and deletion.
    """

    details_requested = Signal(dict)
    mods_changed = Signal()

    def __init__(self, parent=None, api_client=None):
        super().__init__(parent)
        self.api_client = api_client or get_api_client()
        self.all_mods = []
        self.init_ui()

    def init_ui(self):
        """Exécute l'opération init ui."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Header Bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        self.counter_label = QLabel(tr("installed.title"))
        self.counter_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        header_layout.addWidget(self.counter_label)

        self.badge_count = QLabel(tr("installed.badge_count", count=0))
        self.badge_count.setStyleSheet("""
            background-color: #1e293b;
            color: #94a3b8;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 3px 10px;
            font-size: 12px;
            font-weight: 600;
        """)
        header_layout.addWidget(self.badge_count)

        header_layout.addStretch()

        # Search field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("installed.search_placeholder"))
        self.search_input.setFixedWidth(240)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #131726;
                color: #f8fafc;
                border: 1px solid #232d45;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #6366f1;
            }
        """)
        self.search_input.textChanged.connect(self._filter_cards)
        header_layout.addWidget(self.search_input)

        # Scan Button
        self.scan_btn = QPushButton(tr("installed.scan_btn"))
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2438;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 7px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #28314d; color: #ffffff; }
        """)
        self.scan_btn.clicked.connect(self.scan_mods_folder)
        header_layout.addWidget(self.scan_btn)

        # Open Mods Folder Button
        self.open_folder_btn = QPushButton(tr("installed.open_folder_btn"))
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                color: #ffffff;
                border-radius: 8px;
                padding: 7px 16px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #4f46e5); }
        """)
        self.open_folder_btn.clicked.connect(self.open_mods_folder)
        header_layout.addWidget(self.open_folder_btn)

        layout.addLayout(header_layout)

        # 2. Scroll Area for Cards Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        self.card_grid = ResponsiveCardGrid(min_card_width=295, spacing=16)
        scroll.setWidget(self.card_grid)
        layout.addWidget(scroll, stretch=1)

        self.refresh_mods()

    def refresh_mods(self):
        """Fetches installed mods from API and populates grid cards."""
        try:
            res = self.api_client.get_installed_mods()
            self.all_mods = res.get("items", [])
            total = len(self.all_mods)
            self.badge_count.setText(tr("installed.badge_count", count=total))
            self._populate_grid(self.all_mods)
        except Exception as e:
            logger.error(f"Erreur chargement mods installés: {e}")

    def refresh_table(self):
        """Compatibility alias for refresh_mods."""
        self.refresh_mods()

    def _filter_cards(self):
        query = self.search_input.text().strip().lower()
        if not query:
            self._populate_grid(self.all_mods)
            return

        filtered = [
            m
            for m in self.all_mods
            if query in m.get("title", "").lower()
            or query in m.get("folder_name", "").lower()
            or query in m.get("author", "").lower()
            or query in m.get("source", "").lower()
        ]
        self._populate_grid(filtered)

    def _populate_grid(self, mods_list: list):
        if not mods_list:
            self.card_grid.set_empty_message(tr("installed.empty_desc"))
            return

        new_cards = []
        for m in mods_list:
            card = InstalledCard(m, parent=self)
            card.delete_requested.connect(self._on_delete_mod)
            card.open_folder_requested.connect(self.open_mod_folder)
            card.details_requested.connect(self.details_requested.emit)
            new_cards.append(card)

        self.card_grid.set_cards(new_cards)

    def _on_delete_mod(self, mod_data: dict):
        """Confirms with user and uninstalls mod via API, with dependency warning if other mods need it."""
        title = mod_data.get("title", tr("common.untitled"))
        mod_id = mod_data.get("id")
        folder_name = mod_data.get("folder_name", "")

        # 1. Check if other installed mods depend on this mod
        dependents = []
        try:
            dep_res = self.api_client.get_mod_dependents(mod_id)
            dependents = dep_res.get("dependents", [])
        except Exception as e:
            logger.debug(f"Could not check dependents for mod {mod_id}: {e}")

        # 2. Display warning if dependent mods are found
        if dependents:
            dep_lines = "\n".join(f"  • {d.get('title', 'Mod')} ({d.get('folder_name', '')})" for d in dependents)
            confirmed = DialogHelper.confirm(
                self,
                title=tr("installed.dep_warning_title"),
                message=tr("installed.dep_warning_msg", title=title, count=len(dependents), deps=dep_lines),
                confirm_text=tr("installed.btn_delete_anyway"),
                cancel_text=tr("installed.btn_cancel"),
                is_destructive=True,
            )
            if not confirmed:
                return
        else:
            # Standard confirmation
            confirmed = DialogHelper.confirm(
                self,
                title=tr("installed.delete_confirm_title"),
                message=tr("installed.delete_confirm_msg", title=title, folder=folder_name),
                is_destructive=True,
            )
            if not confirmed:
                return

        try:
            res = self.api_client.uninstall_mod(mod_id)
            if res.get("success", False):
                logger.info(f"Mod '{title}' désinstallé avec succès.")
                DialogHelper.success(
                    self, tr("installed.delete_success_title"), tr("installed.delete_success_msg", title=title)
                )
                self.mods_changed.emit()
            else:
                logger.error(f"Échec de la suppression de '{title}': {res.get('message')}")
                DialogHelper.error(self, tr("dialogs.error_title"), res.get("message", tr("dialogs.error_title")))
            self.refresh_mods()
        except Exception as e:
            logger.error(f"Erreur lors de la désinstallation du mod {mod_id}: {e}")
            DialogHelper.error(self, tr("dialogs.error_title"), f"{e}")

    def scan_mods_folder(self):
        """Exécute l'opération scan mods folder."""
        try:
            res = self.api_client.scan_installed_mods()
            msg = res.get("message", "Scan terminé.")
            logger.info(f"Scan des mods effectué : {msg}")
            QMessageBox.information(self, tr("installed.scan_finished_title"), msg)
            self.refresh_mods()
            self.mods_changed.emit()
        except Exception as e:
            logger.error(f"Erreur scan dossier Mods: {e}")
            QMessageBox.critical(self, tr("installed.scan_error_title"), f"{e}")

    def open_mods_folder(self):
        """Exécute l'opération open mods folder."""
        try:
            self.api_client.open_folder()
        except Exception as e:
            QMessageBox.warning(self, tr("dialogs.error_title"), f"{e}")

    def open_mod_folder(self, folder_name: str):
        """Exécute l'opération open mod folder.

        Args:
            folder_name: Paramètre folder_name.
        """
        try:
            self.api_client.open_folder(folder_name=folder_name)
        except Exception as e:
            QMessageBox.warning(self, tr("dialogs.error_title"), f"{e}")

    def retranslate_ui(self):
        """Retranslates all text elements in InstalledView."""
        self.counter_label.setText(tr("installed.title"))
        self.search_input.setPlaceholderText(tr("installed.search_placeholder"))
        self.scan_btn.setText(tr("installed.scan_btn"))
        self.open_folder_btn.setText(tr("installed.open_folder_btn"))
        count = len(self.all_mods)
        self.badge_count.setText(tr("installed.badge_count", count=count))
        self._filter_cards()
