import os
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QCheckBox,
)
from PySide6.QtCore import Qt

from src.core.database import DatabaseManager, InstalledMod
from src.core.config import AppConfig
from src.core.game_detector import GameDetector
from src.core.mod_installer import ModInstaller
from src.core.mod_toggle import ModToggleManager
from src.ui.components.status_badge import StatusBadge
from src.utils.logger import logger

class InstalledView(QWidget):
    """View managing installed Sims 4 mods (toggle, explorer, uninstallation, scanning)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header Bar
        header_layout = QHBoxLayout()
        self.counter_label = QLabel("Chargement des mods...")
        self.counter_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #f8fafc;")
        header_layout.addWidget(self.counter_label)

        header_layout.addStretch()

        # Search field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filtrer les mods installés...")
        self.search_input.setFixedWidth(220)
        self.search_input.textChanged.connect(self.refresh_table)
        header_layout.addWidget(self.search_input)

        # Scan Button
        self.scan_btn = QPushButton("🔄 Scanner le dossier")
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #202436;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #282e48; }
        """)
        self.scan_btn.clicked.connect(self.scan_mods_folder)
        header_layout.addWidget(self.scan_btn)

        # Open Mods Folder Button
        self.open_folder_btn = QPushButton("📁 Dossier Mods")
        self.open_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #6366f1; }
        """)
        self.open_folder_btn.clicked.connect(self.open_mods_folder)
        header_layout.addWidget(self.open_folder_btn)

        layout.addLayout(header_layout)

        # Table of Installed Mods
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Actif",
            "Titre du Mod",
            "Source",
            "Dossier",
            "Fichiers",
            "Date d'installation",
            "Actions",
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.refresh_table()

    def refresh_table(self):
        """Reloads installed mods from SQLite into table."""
        search = self.search_input.text().strip().lower()
        db = DatabaseManager.get_instance()

        with db.get_session() as session:
            query = session.query(InstalledMod)
            if search:
                query = query.filter(
                    (InstalledMod.title.ilike(f"%{search}%")) |
                    (InstalledMod.folder_name.ilike(f"%{search}%"))
                )
            mods = query.order_by(InstalledMod.installed_date.desc()).all()

            total_count = len(mods)
            active_count = sum(1 for m in mods if m.is_enabled)
            self.counter_label.setText(f"Mods Installés ({active_count}/{total_count} actifs)")

            self.table.setRowCount(len(mods))

            for row, mod in enumerate(mods):
                # 0. Active Checkbox
                chk = QCheckBox()
                chk.setChecked(mod.is_enabled)
                chk.setStyleSheet("margin-left: 12px;")
                mod_id = mod.id
                chk.toggled.connect(lambda checked, mid=mod_id: self.toggle_mod(mid, checked))
                self.table.setCellWidget(row, 0, chk)

                # 1. Title
                title_item = QTableWidgetItem(mod.title)
                title_item.setFlags(title_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 1, title_item)

                # 2. Source Badge
                source_widget = QWidget()
                s_layout = QHBoxLayout(source_widget)
                s_layout.setContentsMargins(4, 2, 4, 2)
                s_layout.addWidget(StatusBadge(mod.source.capitalize(), badge_type=mod.source))
                s_layout.addStretch()
                self.table.setCellWidget(row, 2, source_widget)

                # 3. Folder Name
                folder_item = QTableWidgetItem(mod.folder_name)
                folder_item.setFlags(folder_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 3, folder_item)

                # 4. Files Count
                files_list = mod.get_installed_files_list()
                files_item = QTableWidgetItem(f"{len(files_list)} fichier(s)")
                files_item.setFlags(files_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 4, files_item)

                # 5. Install Date
                date_str = mod.installed_date.strftime("%d/%m/%Y %H:%M") if mod.installed_date else "-"
                date_item = QTableWidgetItem(date_str)
                date_item.setFlags(date_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 5, date_item)

                # 6. Actions Widget (Explorer & Delete)
                action_widget = QWidget()
                a_layout = QHBoxLayout(action_widget)
                a_layout.setContentsMargins(4, 2, 4, 2)
                a_layout.setSpacing(6)

                exp_btn = QPushButton("📁")
                exp_btn.setToolTip("Ouvrir ce dossier dans l'Explorateur")
                exp_btn.setFixedWidth(32)
                folder_name = mod.folder_name
                exp_btn.clicked.connect(lambda _, fn=folder_name: self.open_mod_folder(fn))
                a_layout.addWidget(exp_btn)

                del_btn = QPushButton("🗑️")
                del_btn.setToolTip("Désinstaller ce mod")
                del_btn.setFixedWidth(32)
                del_btn.setStyleSheet("background-color: #450a0a; color: #f87171;")
                del_btn.clicked.connect(lambda _, mid=mod_id, t=mod.title: self.uninstall_mod(mid, t))
                a_layout.addWidget(del_btn)

                self.table.setCellWidget(row, 6, action_widget)

    def toggle_mod(self, mod_id: int, state: bool):
        ok, msg = ModToggleManager.toggle_mod(mod_id, target_state=state)
        if not ok:
            QMessageBox.warning(self, "Erreur", msg)
        self.refresh_table()

    def uninstall_mod(self, mod_id: int, title: str):
        reply = QMessageBox.question(
            self,
            "Confirmer la désinstallation",
            f"Êtes-vous sûr de vouloir désinstaller le mod '{title}' ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok, msg = ModInstaller.uninstall_mod(mod_id)
            if ok:
                QMessageBox.information(self, "Succès", msg)
            else:
                QMessageBox.warning(self, "Erreur", msg)
            self.refresh_table()

    def scan_mods_folder(self):
        found = ModInstaller.scan_existing_mods()
        QMessageBox.information(self, "Scan terminé", f"{len(found)} dossier(s) de mods analysé(s) ou synchronisé(s).")
        self.refresh_table()

    def open_mods_folder(self):
        mods_dir = GameDetector.detect_mods_dir(AppConfig.load().custom_mods_dir)
        if mods_dir and mods_dir.exists():
            os.startfile(str(mods_dir))
        else:
            QMessageBox.warning(self, "Erreur", "Dossier Mods introuvable.")

    def open_mod_folder(self, folder_name: str):
        mods_dir = GameDetector.detect_mods_dir(AppConfig.load().custom_mods_dir)
        if mods_dir:
            target = mods_dir / folder_name
            if target.exists():
                os.startfile(str(target))
                return
        QMessageBox.warning(self, "Erreur", f"Le dossier {folder_name} n'existe pas.")
