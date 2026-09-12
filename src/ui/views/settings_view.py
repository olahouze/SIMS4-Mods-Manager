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
    QButtonGroup,
    QScrollArea,
)
from PySide6.QtCore import Qt

from src.api.client import get_api_client
from src.utils.logger import logger
from src.i18n import I18nManager, tr, SUPPORTED_LANGUAGES


class SettingsView(QWidget):
    """Settings page for language, paths, game launcher, backups, and preferences via API."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.i18n = I18nManager.instance()
        self.lang_buttons = {}
        self.init_ui()
        self.i18n.language_changed.connect(self.retranslate_ui)

    def init_ui(self):
        # 1. Main outer layout holding scroll area
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 2. Scroll area for fluid responsive scrolling
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")

        # Responsive centering wrapper
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

        # Common input & button styles
        input_style = """
            QLineEdit {
                background-color: #0f111a;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                min-height: 22px;
            }
            QLineEdit:focus {
                border-color: #6366f1;
            }
        """
        secondary_btn_style = """
            QPushButton {
                background-color: #202436;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: 600;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: #2d334d;
                border-color: #6366f1;
            }
        """

        # Page Title
        self.title_lbl = QLabel(tr("settings.title"))
        self.title_lbl.setStyleSheet("font-size: 20px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(self.title_lbl)

        # 0. Language Selector Section
        self.lang_frame = self._create_section_frame()
        lang_layout = QVBoxLayout(self.lang_frame)
        lang_layout.setContentsMargins(20, 18, 20, 18)
        lang_layout.setSpacing(12)

        self.lang_section_title = QLabel(tr("settings.language_section"))
        self.lang_section_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e8f0;")
        lang_layout.addWidget(self.lang_section_title)

        self.lang_desc_lbl = QLabel(tr("settings.language_desc"))
        self.lang_desc_lbl.setStyleSheet("font-size: 13px; color: #94a3b8;")
        self.lang_desc_lbl.setWordWrap(True)
        lang_layout.addWidget(self.lang_desc_lbl)

        lang_btn_h = QHBoxLayout()
        lang_btn_h.setSpacing(12)

        self.lang_btn_group = QButtonGroup(self)
        self.lang_btn_group.setExclusive(True)

        for code, info in SUPPORTED_LANGUAGES.items():
            btn = QPushButton(f"{info['flag']}  {info['name']}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #cbd5e1;
                    border: 2px solid #334155;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 13px;
                    font-weight: 600;
                    text-align: center;
                    min-width: 130px;
                    min-height: 20px;
                }
                QPushButton:hover {
                    background-color: #334155;
                    color: #ffffff;
                    border-color: #475569;
                }
                QPushButton:checked {
                    background-color: #312e81;
                    color: #ffffff;
                    border-color: #6366f1;
                }
            """)
            btn.clicked.connect(lambda checked, c=code: self._on_language_selected(c))
            self.lang_buttons[code] = btn
            self.lang_btn_group.addButton(btn)
            lang_btn_h.addWidget(btn)

        lang_btn_h.addStretch()
        lang_layout.addLayout(lang_btn_h)
        layout.addWidget(self.lang_frame)

        # 1. Sims 4 Mods Directory Section
        self.mods_frame = self._create_section_frame()
        m_layout = QVBoxLayout(self.mods_frame)
        m_layout.setContentsMargins(20, 18, 20, 18)
        m_layout.setSpacing(12)

        self.mods_section_title = QLabel(tr("settings.mods_folder_section"))
        self.mods_section_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e8f0;")
        m_layout.addWidget(self.mods_section_title)

        path_h = QHBoxLayout()
        path_h.setSpacing(10)
        self.mods_path_input = QLineEdit()
        self.mods_path_input.setStyleSheet(input_style)
        path_h.addWidget(self.mods_path_input, stretch=3)

        self.browse_mods_btn = QPushButton(tr("settings.browse"))
        self.browse_mods_btn.setStyleSheet(secondary_btn_style)
        self.browse_mods_btn.clicked.connect(self.browse_mods_folder)
        path_h.addWidget(self.browse_mods_btn)

        m_layout.addLayout(path_h)

        self.mods_status_lbl = QLabel(tr("settings.checking"))
        self.mods_status_lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
        m_layout.addWidget(self.mods_status_lbl)

        layout.addWidget(self.mods_frame)

        # 2. Game Executable & Launcher Section
        self.game_frame = self._create_section_frame()
        g_layout = QVBoxLayout(self.game_frame)
        g_layout.setContentsMargins(20, 18, 20, 18)
        g_layout.setSpacing(12)

        self.game_section_title = QLabel(tr("settings.game_exe_section"))
        self.game_section_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e8f0;")
        g_layout.addWidget(self.game_section_title)

        exe_h = QHBoxLayout()
        exe_h.setSpacing(10)
        self.exe_path_input = QLineEdit()
        self.exe_path_input.setStyleSheet(input_style)
        exe_h.addWidget(self.exe_path_input, stretch=3)

        self.browse_exe_btn = QPushButton(tr("settings.browse"))
        self.browse_exe_btn.setStyleSheet(secondary_btn_style)
        self.browse_exe_btn.clicked.connect(self.browse_game_exe)
        exe_h.addWidget(self.browse_exe_btn)

        self.launch_btn = QPushButton(tr("nav.launch_game"))
        self.launch_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-weight: 700;
                font-size: 13px;
                min-height: 22px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.launch_btn.clicked.connect(self.launch_game)
        exe_h.addWidget(self.launch_btn)

        g_layout.addLayout(exe_h)
        layout.addWidget(self.game_frame)

        # 3. Preferences Section
        self.pref_frame = self._create_section_frame()
        p_layout = QVBoxLayout(self.pref_frame)
        p_layout.setContentsMargins(20, 18, 20, 18)
        p_layout.setSpacing(14)

        self.pref_section_title = QLabel(tr("settings.options_section"))
        self.pref_section_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e8f0;")
        p_layout.addWidget(self.pref_section_title)

        self.backup_chk = QCheckBox(tr("settings.auto_backup"))
        self.backup_chk.setStyleSheet("font-size: 13px; color: #e2e8f0;")
        p_layout.addWidget(self.backup_chk)

        self.adult_chk = QCheckBox(tr("settings.adult_content"))
        self.adult_chk.setStyleSheet("font-size: 13px; color: #e2e8f0;")
        p_layout.addWidget(self.adult_chk)

        # Cache clear button
        cache_h = QHBoxLayout()
        cache_h.setSpacing(10)
        self.cache_lbl = QLabel(tr("settings.backups_path", path="-"))
        self.cache_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        self.cache_lbl.setWordWrap(True)
        cache_h.addWidget(self.cache_lbl, stretch=3)

        self.clear_cache_btn = QPushButton(tr("settings.clear_cache"))
        self.clear_cache_btn.setStyleSheet(secondary_btn_style)
        self.clear_cache_btn.clicked.connect(self.clear_cache)
        cache_h.addWidget(self.clear_cache_btn)

        p_layout.addLayout(cache_h)
        layout.addWidget(self.pref_frame)

        # 4. Database & Maintenance Section
        self.db_frame = self._create_section_frame()
        db_layout = QVBoxLayout(self.db_frame)
        db_layout.setContentsMargins(20, 18, 20, 18)
        db_layout.setSpacing(14)

        self.db_section_title = QLabel(tr("settings.db_section"))
        self.db_section_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e8f0;")
        db_layout.addWidget(self.db_section_title)

        self.db_stats_lbl = QLabel(tr("settings.db_stats_loading"))
        self.db_stats_lbl.setStyleSheet("font-size: 13px; color: #94a3b8;")
        db_layout.addWidget(self.db_stats_lbl)

        db_actions_h = QHBoxLayout()
        db_actions_h.setSpacing(12)
        self.db_desc_lbl = QLabel(tr("settings.db_purge_desc"))
        self.db_desc_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        self.db_desc_lbl.setWordWrap(True)
        db_actions_h.addWidget(self.db_desc_lbl, stretch=3)

        self.purge_db_btn = QPushButton(tr("settings.purge_db_btn"))
        self.purge_db_btn.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d;
                color: #fecaca;
                border: 1px solid #b91c1c;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: #991b1b;
                color: #ffffff;
            }
        """)
        self.purge_db_btn.clicked.connect(self.confirm_and_purge_database)
        db_actions_h.addWidget(self.purge_db_btn, stretch=1)

        db_layout.addLayout(db_actions_h)
        layout.addWidget(self.db_frame)

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

    def _create_section_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("SettingsSection")
        frame.setStyleSheet("""
            QFrame#SettingsSection {
                background-color: #161824;
                border: 1px solid #282e44;
                border-radius: 12px;
            }
        """)
        return frame

    def _on_language_selected(self, lang_code: str):
        """Called when a language flag button is clicked."""
        if lang_code == self.i18n.get_language():
            return
        logger.info(f"Changement de langue vers: {lang_code}")
        self.i18n.set_language(lang_code)
        # Update settings via API asynchronously
        try:
            self.api_client.update_settings({"language": lang_code})
        except Exception as e:
            logger.error(f"Erreur API lors de la sauvegarde de la langue: {e}")

    def retranslate_ui(self):
        """Retranslates all text in the settings view dynamically."""
        self.title_lbl.setText(tr("settings.title"))
        self.lang_section_title.setText(tr("settings.language_section"))
        self.lang_desc_lbl.setText(tr("settings.language_desc"))
        self.mods_section_title.setText(tr("settings.mods_folder_section"))
        self.browse_mods_btn.setText(tr("settings.browse"))
        self.game_section_title.setText(tr("settings.game_exe_section"))
        self.browse_exe_btn.setText(tr("settings.browse"))
        self.launch_btn.setText(tr("nav.launch_game"))
        self.pref_section_title.setText(tr("settings.options_section"))
        self.backup_chk.setText(tr("settings.auto_backup"))
        self.adult_chk.setText(tr("settings.adult_content"))
        self.clear_cache_btn.setText(tr("settings.clear_cache"))
        self.db_section_title.setText(tr("settings.db_section"))
        self.db_desc_lbl.setText(tr("settings.db_purge_desc"))
        self.purge_db_btn.setText(tr("settings.purge_db_btn"))
        self.save_btn.setText(tr("settings.save_btn"))

        # Re-sync active language button state
        current_lang = self.i18n.get_language()
        if current_lang in self.lang_buttons:
            self.lang_buttons[current_lang].setChecked(True)

        self.load_database_stats()

    def load_settings(self):
        """Loads settings through API /api/settings."""
        try:
            settings = self.api_client.get_settings()
            mods_dir = settings.get("custom_mods_dir") or settings.get("detected_mods_dir") or ""
            exe_path = settings.get("custom_game_exe") or settings.get("detected_game_exe") or ""
            lang = settings.get("language", "fr")

            # Set language button state
            if lang in self.lang_buttons:
                self.lang_buttons[lang].setChecked(True)
                if self.i18n.get_language() != lang:
                    self.i18n.set_language(lang)

            self.mods_path_input.setText(mods_dir)
            self.exe_path_input.setText(exe_path)
            self.backup_chk.setChecked(settings.get("auto_backup", True))
            self.adult_chk.setChecked(settings.get("adult_content_enabled", True))

            backups_dir = settings.get("backups_dir", "")
            self.cache_lbl.setText(tr("settings.backups_path", path=backups_dir))

            has_valid_mods = bool(settings.get("detected_mods_dir"))
            self.mods_status_lbl.setText(
                tr("settings.folder_valid") if has_valid_mods else tr("settings.folder_invalid")
            )
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
                tr("settings.db_stats", catalog=cat_count, installed=inst_count)
            )
        except Exception as e:
            logger.debug(f"Impossible de charger les statistiques de base de données : {e}")
            self.db_stats_lbl.setText(tr("settings.db_stats_error"))

    def confirm_and_purge_database(self):
        """Displays confirmation dialog and purges the catalog database if confirmed."""
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
                QMessageBox.warning(
                    self,
                    tr("dialogs.error_title"),
                    tr("settings.purge_error", error=str(e)),
                )

    def browse_mods_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, tr("settings.select_mods_dir"))
        if dir_path:
            self.mods_path_input.setText(dir_path)

    def browse_game_exe(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("settings.select_game_exe"), "", "Exécutables (*.exe)"
        )
        if file_path:
            self.exe_path_input.setText(file_path)

    def launch_game(self):
        try:
            res = self.api_client.launch_game()
            QMessageBox.information(
                self, tr("nav.launch_game_title"), res.get("message", tr("nav.launch_game_success"))
            )
        except Exception as e:
            QMessageBox.warning(
                self, tr("dialogs.error_title"), tr("nav.launch_game_error", error=str(e))
            )

    def clear_cache(self):
        try:
            res = self.api_client.clear_cache()
            count = res.get("deleted_count", 0)
            QMessageBox.information(
                self, tr("settings.clear_cache_title"), tr("settings.clear_cache_success", count=count)
            )
        except Exception as e:
            QMessageBox.warning(
                self, tr("dialogs.error_title"), tr("settings.clear_cache_error", error=str(e))
            )

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
            QMessageBox.information(
                self, tr("settings.save_success_title"), tr("settings.save_success_msg")
            )
            self.load_settings()
        except Exception as e:
            QMessageBox.warning(
                self, tr("settings.save_error_title"), tr("settings.save_error_msg", error=str(e))
            )
