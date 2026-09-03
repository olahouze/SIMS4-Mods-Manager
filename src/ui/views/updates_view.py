from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)
from PySide6.QtCore import Qt

from src.core.database import DatabaseManager, InstalledMod, CatalogMod
from src.ui.components.status_badge import StatusBadge
from src.ui.components.progress_dialog import ProgressDialog
from src.ui.views.catalog_view import InstallWorker

class UpdatesView(QWidget):
    """View displaying installed mods with newer versions available and 1-click updates."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header Bar
        header_layout = QHBoxLayout()
        self.counter_label = QLabel("Recherche des mises à jour...")
        self.counter_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #f8fafc;")
        header_layout.addWidget(self.counter_label)

        header_layout.addStretch()

        self.update_all_btn = QPushButton("⚡ Tout Mettre à Jour")
        self.update_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #eab308;
                color: #000000;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #facc15; }
        """)
        self.update_all_btn.clicked.connect(self.update_all_mods)
        header_layout.addWidget(self.update_all_btn)

        layout.addLayout(header_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Titre du Mod",
            "Source",
            "Version Actuelle",
            "Nouvelle Version",
            "Date MàJ",
            "Action",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.refresh_updates()

    def refresh_updates(self):
        """Finds all installed mods having updates in catalog."""
        db = DatabaseManager.get_instance()
        self.updatable_mods = []

        with db.get_session() as session:
            installed_list = session.query(InstalledMod).all()
            for im in installed_list:
                cat_mod = None
                if im.catalog_mod_id:
                    cat_mod = session.query(CatalogMod).filter_by(id=im.catalog_mod_id).first()
                elif im.remote_id:
                    cat_mod = session.query(CatalogMod).filter_by(source=im.source, remote_id=im.remote_id).first()

                if cat_mod and cat_mod.updated_date and im.version_date:
                    if cat_mod.updated_date > im.version_date:
                        self.updatable_mods.append({
                            "installed": im,
                            "catalog": cat_mod,
                        })

            count = len(self.updatable_mods)
            self.counter_label.setText(f"{count} Mise(s) à jour disponible(s)")
            self.update_all_btn.setEnabled(count > 0)

            self.table.setRowCount(count)

            for row, item in enumerate(self.updatable_mods):
                im = item["installed"]
                cm = item["catalog"]

                # 0. Title
                self.table.setItem(row, 0, QTableWidgetItem(im.title))

                # 1. Source
                src_widget = QWidget()
                s_layout = QHBoxLayout(src_widget)
                s_layout.setContentsMargins(4, 2, 4, 2)
                s_layout.addWidget(StatusBadge(im.source.capitalize(), badge_type=im.source))
                s_layout.addStretch()
                self.table.setCellWidget(row, 1, src_widget)

                # 2. Current version date
                cur_date = im.version_date.strftime("%d/%m/%Y") if im.version_date else "Inconnue"
                self.table.setItem(row, 2, QTableWidgetItem(cur_date))

                # 3. New version date
                new_date = cm.updated_date.strftime("%d/%m/%Y") if cm.updated_date else "Récente"
                self.table.setItem(row, 3, QTableWidgetItem(new_date))

                # 4. Status
                status_item = QTableWidgetItem("Nouveau fichier disponible")
                self.table.setItem(row, 4, status_item)

                # 5. Update Button
                up_btn = QPushButton("🔄 Mettre à jour")
                up_btn.setStyleSheet("background-color: #6366f1; color: #fff; font-weight: 600; border-radius: 4px; padding: 4px 10px;")
                mod_data = {
                    "source": cm.source,
                    "remote_id": cm.remote_id,
                    "title": cm.title,
                    "page_url": cm.page_url,
                    "updated_date": cm.updated_date,
                }
                up_btn.clicked.connect(lambda _, md=mod_data: self.update_single_mod(md))
                self.table.setCellWidget(row, 5, up_btn)

    def update_single_mod(self, mod_data: dict):
        self.progress_dlg = ProgressDialog(f"Mise à jour de {mod_data.get('title')}", self)
        self.progress_dlg.show()

        self.worker = InstallWorker(mod_data)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, msg: str, percent: int):
        if hasattr(self, 'progress_dlg') and self.progress_dlg.isVisible():
            self.progress_dlg.set_status(msg)
            self.progress_dlg.set_progress(percent)

    def _on_finished(self, success: bool, msg: str):
        if hasattr(self, 'progress_dlg'):
            self.progress_dlg.close()
        if success:
            QMessageBox.information(self, "Mise à jour réussie", msg)
        else:
            QMessageBox.warning(self, "Erreur de mise à jour", msg)
        self.refresh_updates()

    def update_all_mods(self):
        if not self.updatable_mods:
            return
        reply = QMessageBox.question(
            self,
            "Tout mettre à jour",
            f"Voulez-vous mettre à jour les {len(self.updatable_mods)} mods avec sauvegarde automatique ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Process sequentially
            first_mod = self.updatable_mods[0]["catalog"]
            self.update_single_mod({
                "source": first_mod.source,
                "remote_id": first_mod.remote_id,
                "title": first_mod.title,
                "page_url": first_mod.page_url,
                "updated_date": first_mod.updated_date,
            })
