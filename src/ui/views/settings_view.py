from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QFrame,
)

from src.api.client import get_api_client
from src.utils.logger import logger


class SettingsView(QWidget):
    """Settings page for paths, game launcher, backups, and preferences via API."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        title = QLabel("Paramètres de l'Application")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title)

        # 1. Sims 4 Mods Directory Section
        mods_frame = self._create_section_frame("Dossier des Mods Les Sims 4")
        m_layout = QVBoxLayout(mods_frame)

        path_h = QHBoxLayout()
        self.mods_path_input = QLineEdit()
        path_h.addWidget(self.mods_path_input, stretch=3)

        browse_mods_btn = QPushButton("Parcourir...")
        browse_mods_btn.setStyleSheet(
            "background-color: #202436; color: #f1f5f9; padding: 8px 14px; border-radius: 6px;"
        )
        browse_mods_btn.clicked.connect(self.browse_mods_folder)
        path_h.addWidget(browse_mods_btn)

        m_layout.addLayout(path_h)

        self.mods_status_lbl = QLabel("Vérification...")
        m_layout.addWidget(self.mods_status_lbl)

        layout.addWidget(mods_frame)

        # 2. Game Executable & Launcher Section
        game_frame = self._create_section_frame("Exécutable du Jeu & Lanceur")
        g_layout = QVBoxLayout(game_frame)

        exe_h = QHBoxLayout()
        self.exe_path_input = QLineEdit()
        exe_h.addWidget(self.exe_path_input, stretch=3)

        browse_exe_btn = QPushButton("Parcourir...")
        browse_exe_btn.setStyleSheet(
            "background-color: #202436; color: #f1f5f9; padding: 8px 14px; border-radius: 6px;"
        )
        browse_exe_btn.clicked.connect(self.browse_game_exe)
        exe_h.addWidget(browse_exe_btn)

        launch_btn = QPushButton("▶ Lancer Les Sims 4")
        launch_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        launch_btn.clicked.connect(self.launch_game)
        exe_h.addWidget(launch_btn)

        g_layout.addLayout(exe_h)
        layout.addWidget(game_frame)

        # 3. Preferences Section
        pref_frame = self._create_section_frame("Options & Sauvegardes")
        p_layout = QVBoxLayout(pref_frame)
        p_layout.setSpacing(12)

        self.backup_chk = QCheckBox(
            "Créer automatiquement une sauvegarde (.zip) de l'ancienne version avant mise à jour"
        )
        p_layout.addWidget(self.backup_chk)

        self.adult_chk = QCheckBox("Activer les contenus adultes / NSFW (+18 ans) sur LoversLab")
        p_layout.addWidget(self.adult_chk)

        # Cache clear button
        cache_h = QHBoxLayout()
        self.cache_lbl = QLabel("Emplacement des sauvegardes : -")
        self.cache_lbl.setStyleSheet("font-size: 11px; color: #64748b;")
        cache_h.addWidget(self.cache_lbl)
        cache_h.addStretch()

        clear_cache_btn = QPushButton("🗑️ Vider le cache des miniatures")
        clear_cache_btn.setStyleSheet(
            "background-color: #202436; color: #94a3b8; padding: 6px 12px; border-radius: 6px;"
        )
        clear_cache_btn.clicked.connect(self.clear_cache)
        cache_h.addWidget(clear_cache_btn)

        p_layout.addLayout(cache_h)
        layout.addWidget(pref_frame)

        # 4. Database & Maintenance Section
        db_frame = self._create_section_frame("Base de Données & Maintenance")
        db_layout = QVBoxLayout(db_frame)
        db_layout.setSpacing(12)

        self.db_stats_lbl = QLabel("Catalogue : Chargement des statistiques...")
        self.db_stats_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        db_layout.addWidget(self.db_stats_lbl)

        db_actions_h = QHBoxLayout()
        db_desc_lbl = QLabel(
            "Réinitialiser le catalogue local en cas d'incohérences ou pour relancer un scan propre. "
            "Vos fichiers de mods réels ne seront pas supprimés."
        )
        db_desc_lbl.setStyleSheet("font-size: 11px; color: #64748b;")
        db_desc_lbl.setWordWrap(True)
        db_actions_h.addWidget(db_desc_lbl, stretch=3)

        purge_db_btn = QPushButton("🗑️ Purger la base de données")
        purge_db_btn.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d;
                color: #fecaca;
                border: 1px solid #b91c1c;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #991b1b;
                color: #ffffff;
            }
        """)
        purge_db_btn.clicked.connect(self.confirm_and_purge_database)
        db_actions_h.addWidget(purge_db_btn, stretch=1)

        db_layout.addLayout(db_actions_h)
        layout.addWidget(db_frame)

        # Save Button
        save_btn = QPushButton("💾 Enregistrer les Paramètres")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border-radius: 8px;
                padding: 10px 24px;
                font-weight: 700;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #6366f1; }
        """)
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()

        self.load_settings()

    def _create_section_frame(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #161824;
                border: 1px solid #282e44;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        return frame

    def load_settings(self):
        """Loads settings through API /api/settings."""
        try:
            settings = self.api_client.get_settings()
            mods_dir = settings.get("custom_mods_dir") or settings.get("detected_mods_dir") or ""
            exe_path = settings.get("custom_game_exe") or settings.get("detected_game_exe") or ""

            self.mods_path_input.setText(mods_dir)
            self.exe_path_input.setText(exe_path)
            self.backup_chk.setChecked(settings.get("auto_backup", True))
            self.adult_chk.setChecked(settings.get("adult_content_enabled", True))

            backups_dir = settings.get("backups_dir", "")
            self.cache_lbl.setText(f"Emplacement des sauvegardes : {backups_dir}")

            has_valid_mods = bool(settings.get("detected_mods_dir"))
            self.mods_status_lbl.setText("✓ Dossier détecté et valide" if has_valid_mods else "⚠️ Dossier non détecté")
            self.mods_status_lbl.setStyleSheet("color: #34d399;" if has_valid_mods else "color: #f87171;")

            self.load_database_stats()

        except Exception as e:
            logger.error(f"Erreur API lors du chargement des paramètres: {e}")

    def load_database_stats(self):
        """Fetches and displays current catalog and installed database counts."""
        try:
            stats = self.api_client.get_database_stats()
            cat_count = stats.get("catalog_mods_count", 0)
            inst_count = stats.get("installed_mods_count", 0)
            self.db_stats_lbl.setText(
                f"📊 Catalogue : {cat_count} mod(s) indexé(s) | Mods installés suivis : {inst_count}"
            )
        except Exception as e:
            logger.debug(f"Impossible de charger les statistiques de base de données : {e}")
            self.db_stats_lbl.setText("Catalogue : Impossible d'obtenir les statistiques.")

    def confirm_and_purge_database(self):
        """Displays confirmation dialog and purges the catalog database if confirmed."""
        reply = QMessageBox.question(
            self,
            "Confirmation de purge de la base de données",
            "Êtes-vous sûr de vouloir purger le catalogue de la base de données ?\n\n"
            "• Tous les mods indexés dans le catalogue local seront supprimés.\n"
            "• Vos fichiers physiques de mods dans le dossier Les Sims 4 ne seront PAS supprimés.\n"
            "• Une nouvelle synchronisation sera nécessaire pour explorer le catalogue.\n\n"
            "Souhaitez-vous continuer ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                res = self.api_client.purge_database()
                deleted = res.get("deleted_count", 0)
                QMessageBox.information(
                    self,
                    "Base de données purgée",
                    f"La base de données a été purgée avec succès.\n{deleted} mod(s) supprimé(s) du catalogue.",
                )
                self.load_database_stats()
            except Exception as e:
                logger.error(f"Erreur lors de la purge de la base de données : {e}")
                QMessageBox.warning(self, "Erreur", f"Échec de la purge de la base de données via l'API: {e}")

    def browse_mods_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier Mods de Sims 4")
        if dir_path:
            self.mods_path_input.setText(dir_path)

    def browse_game_exe(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Sélectionner l'exécutable Sims 4", "", "Exécutables (*.exe)")
        if file_path:
            self.exe_path_input.setText(file_path)

    def launch_game(self):
        try:
            res = self.api_client.launch_game()
            QMessageBox.information(self, "Lancement", res.get("message", "Jeu lancé."))
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Impossible de lancer Les Sims 4 via l'API: {e}")

    def clear_cache(self):
        try:
            res = self.api_client.clear_cache()
            QMessageBox.information(self, "Cache Vidé", res.get("message", "Cache vidé."))
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Échec du vidage de cache via l'API: {e}")

    def save_settings(self):
        payload = {
            "custom_mods_dir": self.mods_path_input.text().strip() or None,
            "custom_game_exe": self.exe_path_input.text().strip() or None,
            "auto_backup": self.backup_chk.isChecked(),
            "adult_content_enabled": self.adult_chk.isChecked(),
        }
        try:
            self.api_client.update_settings(payload)
            QMessageBox.information(self, "Succès", "Paramètres enregistrés avec succès via l'API !")
            self.load_settings()
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Échec de l'enregistrement des paramètres via l'API: {e}")
