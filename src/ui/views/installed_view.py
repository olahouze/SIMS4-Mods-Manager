from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QGridLayout,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from src.api.client import get_api_client
from src.ui.components.installed_card import InstalledCard
from src.utils.logger import logger


class InstalledView(QWidget):
    """
    Modern grid view managing installed Sims 4 mods.
    Displays rich cards with cover previews, metadata, direct folder access, and deletion.
    """

    details_requested = Signal(dict)
    mods_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.all_mods = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Header Bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        self.counter_label = QLabel("Mes Mods Installés")
        self.counter_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        header_layout.addWidget(self.counter_label)

        self.badge_count = QLabel("0 mod")
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
        self.search_input.setPlaceholderText("🔍 Filtrer mes mods installés...")
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
        self.scan_btn = QPushButton("🔄 Scanner le dossier")
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
        self.open_folder_btn = QPushButton("📁 Dossier Mods")
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
        scroll.setStyleSheet("background-color: transparent; border: none;")

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll, stretch=1)

        self.refresh_mods()

    def refresh_mods(self):
        """Fetches installed mods from API and populates grid cards."""
        try:
            res = self.api_client.get_installed_mods()
            self.all_mods = res.get("items", [])
            total = len(self.all_mods)
            self.badge_count.setText(f"{total} mod{'s' if total > 1 else ''}")
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
        # Clear existing items
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not mods_list:
            no_mods_lbl = QLabel(
                "Aucun mod installé trouvé.\n"
                "Parcourez le catalogue ou placez vos mods dans le dossier Mods pour les voir ici !"
            )
            no_mods_lbl.setStyleSheet("font-size: 14px; color: #64748b; padding: 40px;")
            no_mods_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_mods_lbl, 0, 0)
            return

        columns = 4
        row = 0
        col = 0

        for m in mods_list:
            card = InstalledCard(m, parent=self)
            card.delete_requested.connect(self._on_delete_mod)
            card.open_folder_requested.connect(self.open_mod_folder)
            card.details_requested.connect(self.details_requested.emit)
            self.grid_layout.addWidget(card, row, col)

            col += 1
            if col >= columns:
                col = 0
                row += 1

    def _on_delete_mod(self, mod_data: dict):
        """Confirms with user and uninstalls mod via API."""
        title = mod_data.get("title", "ce mod")
        mod_id = mod_data.get("id")
        folder_name = mod_data.get("folder_name", "")

        reply = QMessageBox.question(
            self,
            "Confirmer la suppression",
            f"Voulez-vous vraiment désinstaller et supprimer définitivement le mod suivant ?\n\n"
            f"• Titre : {title}\n"
            f"• Dossier : {folder_name}\n\n"
            f"Le dossier physique et tous ses fichiers seront supprimés de votre jeu Sims 4.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                res = self.api_client.uninstall_mod(mod_id)
                if res.get("success", False):
                    logger.info(f"Mod '{title}' désinstallé avec succès.")
                    QMessageBox.information(self, "Mod Supprimé", f"Le mod '{title}' a été supprimé avec succès.")
                    self.mods_changed.emit()
                else:
                    logger.error(f"Échec de la suppression de '{title}': {res.get('message')}")
                    QMessageBox.warning(self, "Erreur", res.get("message", "Échec de la suppression."))
                self.refresh_mods()
            except Exception as e:
                logger.error(f"Erreur lors de la désinstallation du mod {mod_id}: {e}")
                QMessageBox.critical(self, "Erreur", f"Une erreur est survenue: {e}")

    def scan_mods_folder(self):
        try:
            res = self.api_client.scan_installed_mods()
            msg = res.get("message", "Scan terminé.")
            logger.info(f"Scan des mods effectué : {msg}")
            QMessageBox.information(self, "Scan Terminé", msg)
            self.refresh_mods()
            self.mods_changed.emit()
        except Exception as e:
            logger.error(f"Erreur scan dossier Mods: {e}")
            QMessageBox.critical(self, "Erreur Scan", f"Impossible de scanner le dossier Mods: {e}")

    def open_mods_folder(self):
        try:
            self.api_client.open_folder()
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Impossible d'ouvrir le dossier Mods: {e}")

    def open_mod_folder(self, folder_name: str):
        try:
            self.api_client.open_folder(folder_name=folder_name)
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Impossible d'ouvrir le sous-dossier '{folder_name}': {e}")
