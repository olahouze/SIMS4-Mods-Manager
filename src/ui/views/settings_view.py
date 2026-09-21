"""
Settings page for language, paths, game launcher, backups, and preferences via REST API.
Composed of specialized card sections for maximum modularity and visual polish.
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QFrame,
)

from src.api.client import get_api_client
from src.utils.logger import logger
from src.i18n import I18nManager, tr
from src.ui.views.settings.settings_cards import (
    LanguageCardWidget,
    PathsCardWidget,
    GameLauncherCardWidget,
    PreferencesCardWidget,
    DatabaseCardWidget,
)


class SettingsView(QWidget):
    """Settings page orchestrating language, game paths, launcher, and backup cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.i18n = I18nManager.instance()
        self._has_valid_mods = False
        self._backups_dir = ""

        self.init_ui()
        self.i18n.language_changed.connect(self.retranslate_ui)

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")

        wrapper_layout = QHBoxLayout(container)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)

        inner_widget = QWidget()
        inner_widget.setMaximumWidth(960)
        layout = QVBoxLayout(inner_widget)
        layout.setContentsMargins(28, 28, 28, 36)
        layout.setSpacing(22)

        wrapper_layout.addStretch(1)
        wrapper_layout.addWidget(inner_widget, stretch=12)
        wrapper_layout.addStretch(1)

        self.scroll_area.setWidget(container)
        root_layout.addWidget(self.scroll_area)

        # Main Page Title
        self.title_lbl = QLabel(tr("settings.title"))
        self.title_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #f8fafc;")
        layout.addWidget(self.title_lbl)

        # 1. Language Card
        self.lang_card = LanguageCardWidget(self._on_language_selected, parent=self)
        self.lang_buttons = self.lang_card.lang_buttons
        self.lang_frame = self.lang_card
        layout.addWidget(self.lang_card)

        # 2. Paths Card (Sims 4 Mods Folder)
        self.paths_card = PathsCardWidget(
            on_browse=self.browse_mods_folder,
            on_path_changed=self._on_mods_path_changed,
            parent=self,
        )
        self.mods_path_input = self.paths_card.mods_path_input
        self.browse_mods_btn = self.paths_card.browse_mods_btn
        self.mods_status_lbl = self.paths_card.mods_status_lbl
        self.mods_frame = self.paths_card
        layout.addWidget(self.paths_card)

        # 3. Game Launcher Card
        self.launcher_card = GameLauncherCardWidget(
            on_browse_exe=self.browse_game_exe,
            on_launch=self.launch_game,
            parent=self,
        )
        self.exe_path_input = self.launcher_card.exe_path_input
        self.browse_exe_btn = self.launcher_card.browse_exe_btn
        self.launch_btn = self.launcher_card.launch_btn
        self.game_frame = self.launcher_card
        layout.addWidget(self.launcher_card)

        # 4. Preferences Card
        self.pref_card = PreferencesCardWidget(on_clear_cache=self.clear_cache, parent=self)
        self.backup_chk = self.pref_card.backup_chk
        self.adult_chk = self.pref_card.adult_chk
        self.cache_lbl = self.pref_card.cache_lbl
        self.clear_cache_btn = self.pref_card.clear_cache_btn
        self.pref_frame = self.pref_card
        layout.addWidget(self.pref_card)

        # 5. Database Card
        self.db_card = DatabaseCardWidget(on_purge=self.confirm_and_purge_database, parent=self)
        self.db_stats_lbl = self.db_card.db_stats_lbl
        self.db_desc_lbl = self.db_card.db_desc_lbl
        self.purge_db_btn = self.db_card.purge_db_btn
        self.db_frame = self.db_card
        layout.addWidget(self.db_card)

        # Save Button
        self.save_btn = QPushButton(tr("settings.save_btn"))
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 12px 28px;
                font-weight: 700;
                font-size: 14px;
                min-height: 22px;
            }
            QPushButton:hover { background-color: #6366f1; }
        """)
        self.save_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_btn)

        layout.addStretch()
        self.load_settings()

    def _on_language_selected(self, lang_code: str):
        if lang_code == self.i18n.get_language():
            return
        logger.info(f"Changement de langue vers: {lang_code}")
        self.i18n.set_language(lang_code)
        try:
            self.api_client.update_settings({"language": lang_code})
        except Exception as e:
            logger.error(f"Erreur API lors de la sauvegarde de la langue: {e}")

    def _on_mods_path_changed(self, text: str):
        p = Path(text.strip()) if text.strip() else None
        self._has_valid_mods = bool(p and p.exists() and p.is_dir())
        self.paths_card.update_status(self._has_valid_mods)

    def retranslate_ui(self):
        """Retranslates all child card components dynamically."""
        self.title_lbl.setText(tr("settings.title"))
        current_lang = self.i18n.get_language()
        self.lang_card.retranslate_ui(current_lang)
        self.paths_card.retranslate_ui(self._has_valid_mods)
        self.launcher_card.retranslate_ui()
        self.pref_card.retranslate_ui(self._backups_dir)
        self.db_card.retranslate_ui()
        self.save_btn.setText(tr("settings.save_btn"))
        self.load_database_stats()

    def load_settings(self):
        """Loads settings through API /api/settings."""
        try:
            settings = self.api_client.get_settings()
            mods_dir = settings.get("custom_mods_dir") or settings.get("detected_mods_dir") or ""
            exe_path = settings.get("custom_game_exe") or settings.get("detected_game_exe") or ""
            lang = settings.get("language", "fr")

            if lang in self.lang_buttons:
                self.lang_buttons[lang].setChecked(True)
                if self.i18n.get_language() != lang:
                    self.i18n.set_language(lang)

            self.mods_path_input.setText(mods_dir)
            self.exe_path_input.setText(exe_path)
            self.backup_chk.setChecked(settings.get("auto_backup", True))
            self.adult_chk.setChecked(settings.get("adult_content_enabled", True))

            self._backups_dir = settings.get("backups_dir", "")
            self.cache_lbl.setText(tr("settings.backups_path", path=self._backups_dir or "-"))

            self._has_valid_mods = bool(settings.get("detected_mods_dir"))
            self.paths_card.update_status(self._has_valid_mods)
            self.load_database_stats()
        except Exception as e:
            logger.error(f"Erreur API lors du chargement des paramètres: {e}")

    def load_database_stats(self):
        """Fetches and displays current catalog and installed database counts."""
        try:
            stats = self.api_client.get_database_stats()
            cat_count = stats.get("catalog_mods_count", 0)
            inst_count = stats.get("installed_mods_count", 0)
            self.db_stats_lbl.setText(tr("settings.db_stats", catalog=cat_count, installed=inst_count))
        except Exception as e:
            logger.debug(f"Impossible de charger les statistiques de base de données : {e}")
            self.db_stats_lbl.setText(tr("settings.db_stats_error"))

    def confirm_and_purge_database(self):
        reply = QMessageBox.question(
            self,
            tr("settings.purge_confirm_title"),
            tr("settings.purge_confirm_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                res = self.api_client.purge_database()
                deleted = res.get("deleted_count", 0)
                QMessageBox.information(
                    self,
                    tr("settings.purge_success_title"),
                    tr("settings.purge_success_msg", count=deleted),
                )
                self.load_database_stats()
            except Exception as e:
                logger.error(f"Erreur lors de la purge de la base de données : {e}")
                QMessageBox.warning(self, tr("dialogs.error_title"), tr("settings.purge_error", error=str(e)))

    def browse_mods_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, tr("settings.select_mods_dir"))
        if dir_path:
            self.mods_path_input.setText(dir_path)
            self._on_mods_path_changed(dir_path)

    def browse_game_exe(self):
        file_path, _ = QFileDialog.getOpenFileName(self, tr("settings.select_game_exe"), "", tr("settings.exe_filter"))
        if file_path:
            self.exe_path_input.setText(file_path)

    def launch_game(self):
        try:
            res = self.api_client.launch_game()
            QMessageBox.information(
                self, tr("nav.launch_game_title"), res.get("message", tr("nav.launch_game_success"))
            )
        except Exception as e:
            QMessageBox.warning(self, tr("dialogs.error_title"), tr("nav.launch_game_error", error=str(e)))

    def clear_cache(self):
        try:
            res = self.api_client.clear_cache()
            count = res.get("deleted_count", 0)
            QMessageBox.information(
                self, tr("settings.clear_cache_title"), tr("settings.clear_cache_success", count=count)
            )
        except Exception as e:
            QMessageBox.warning(self, tr("dialogs.error_title"), tr("settings.clear_cache_error", error=str(e)))

    def save_settings(self):
        current_lang = self.i18n.get_language()
        payload = {
            "custom_mods_dir": self.mods_path_input.text().strip() or None,
            "custom_game_exe": self.exe_path_input.text().strip() or None,
            "auto_backup": self.backup_chk.isChecked(),
            "adult_content_enabled": self.adult_chk.isChecked(),
            "language": current_lang,
        }
        try:
            self.api_client.update_settings(payload)
            QMessageBox.information(self, tr("settings.save_success_title"), tr("settings.save_success_msg"))
            self.load_settings()
        except Exception as e:
            QMessageBox.warning(self, tr("settings.save_error_title"), tr("settings.save_error_msg", error=str(e)))
