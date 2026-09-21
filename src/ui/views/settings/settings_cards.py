"""
Specialized settings section card widgets for SIMS 4 Mods Manager.
"""

from typing import Callable, Dict
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QButtonGroup,
)
from PySide6.QtCore import Qt

from src.i18n import tr, SUPPORTED_LANGUAGES
from src.ui.theme import Theme


def create_section_frame() -> QFrame:
    """Creates a standard dark card frame for a settings section."""
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


class LanguageCardWidget(QFrame):
    """Card widget for language selection with country flag buttons."""

    def __init__(self, on_language_selected: Callable[[str], None], parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsSection")
        self.setStyleSheet(create_section_frame().styleSheet())
        self.on_language_selected = on_language_selected
        self.lang_buttons: Dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        self.title_lbl = QLabel(tr("settings.language_section"))
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e8f0;")
        layout.addWidget(self.title_lbl)

        self.desc_lbl = QLabel(tr("settings.language_desc"))
        self.desc_lbl.setStyleSheet("font-size: 13px; color: #94a3b8;")
        self.desc_lbl.setWordWrap(True)
        layout.addWidget(self.desc_lbl)

        lang_btn_h = QHBoxLayout()
        lang_btn_h.setSpacing(12)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

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
            btn.clicked.connect(lambda checked, c=code: self.on_language_selected(c))
            self.lang_buttons[code] = btn
            self.btn_group.addButton(btn)
            lang_btn_h.addWidget(btn)

        lang_btn_h.addStretch()
        layout.addLayout(lang_btn_h)

    def retranslate_ui(self, current_lang: str):
        self.title_lbl.setText(tr("settings.language_section"))
        self.desc_lbl.setText(tr("settings.language_desc"))
        for code, btn in self.lang_buttons.items():
            btn.setChecked(code == current_lang)


class PathsCardWidget(QFrame):
    """Card widget for configuring and validating the Sims 4 Mods folder."""

    def __init__(self, on_browse: Callable[[], None], on_path_changed: Callable[[str], None], parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsSection")
        self.setStyleSheet(create_section_frame().styleSheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        self.title_lbl = QLabel(tr("settings.mods_folder_section"))
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e8f0;")
        layout.addWidget(self.title_lbl)

        path_h = QHBoxLayout()
        path_h.setSpacing(10)
        self.mods_path_input = QLineEdit()
        self.mods_path_input.setStyleSheet(Theme.input_style())
        self.mods_path_input.textChanged.connect(on_path_changed)
        path_h.addWidget(self.mods_path_input, stretch=3)

        self.browse_mods_btn = QPushButton(tr("settings.browse"))
        self.browse_mods_btn.setStyleSheet(Theme.secondary_button_style())
        self.browse_mods_btn.clicked.connect(on_browse)
        path_h.addWidget(self.browse_mods_btn)
        layout.addLayout(path_h)

        self.mods_status_lbl = QLabel(tr("settings.checking"))
        self.mods_status_lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
        layout.addWidget(self.mods_status_lbl)

    def retranslate_ui(self, is_valid: bool):
        self.title_lbl.setText(tr("settings.mods_folder_section"))
        self.browse_mods_btn.setText(tr("settings.browse"))
        self.update_status(is_valid)

    def update_status(self, is_valid: bool):
        self.mods_status_lbl.setText(tr("settings.folder_valid") if is_valid else tr("settings.folder_invalid"))
        self.mods_status_lbl.setStyleSheet("color: #34d399;" if is_valid else "color: #f87171;")


class GameLauncherCardWidget(QFrame):
    """Card widget for Sims 4 game executable path and direct launch."""

    def __init__(self, on_browse_exe: Callable[[], None], on_launch: Callable[[], None], parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsSection")
        self.setStyleSheet(create_section_frame().styleSheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        self.title_lbl = QLabel(tr("settings.game_exe_section"))
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e8f0;")
        layout.addWidget(self.title_lbl)

        exe_h = QHBoxLayout()
        exe_h.setSpacing(10)
        self.exe_path_input = QLineEdit()
        self.exe_path_input.setStyleSheet(Theme.input_style())
        exe_h.addWidget(self.exe_path_input, stretch=3)

        self.browse_exe_btn = QPushButton(tr("settings.browse"))
        self.browse_exe_btn.setStyleSheet(Theme.secondary_button_style())
        self.browse_exe_btn.clicked.connect(on_browse_exe)
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
        self.launch_btn.clicked.connect(on_launch)
        exe_h.addWidget(self.launch_btn)

        layout.addLayout(exe_h)

    def retranslate_ui(self):
        self.title_lbl.setText(tr("settings.game_exe_section"))
        self.browse_exe_btn.setText(tr("settings.browse"))
        self.launch_btn.setText(tr("nav.launch_game"))


class PreferencesCardWidget(QFrame):
    """Card widget for options: auto-backup, adult content, cache clearance."""

    def __init__(self, on_clear_cache: Callable[[], None], parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsSection")
        self.setStyleSheet(create_section_frame().styleSheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        self.title_lbl = QLabel(tr("settings.options_section"))
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e8f0;")
        layout.addWidget(self.title_lbl)

        self.backup_chk = QCheckBox(tr("settings.auto_backup"))
        self.backup_chk.setStyleSheet("font-size: 13px; color: #e2e8f0;")
        layout.addWidget(self.backup_chk)

        self.adult_chk = QCheckBox(tr("settings.adult_content"))
        self.adult_chk.setStyleSheet("font-size: 13px; color: #e2e8f0;")
        layout.addWidget(self.adult_chk)

        cache_h = QHBoxLayout()
        cache_h.setSpacing(10)
        self.cache_lbl = QLabel(tr("settings.backups_path", path="-"))
        self.cache_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        self.cache_lbl.setWordWrap(True)
        cache_h.addWidget(self.cache_lbl, stretch=3)

        self.clear_cache_btn = QPushButton(tr("settings.clear_cache"))
        self.clear_cache_btn.setStyleSheet(Theme.secondary_button_style())
        self.clear_cache_btn.clicked.connect(on_clear_cache)
        cache_h.addWidget(self.clear_cache_btn)
        layout.addLayout(cache_h)

    def retranslate_ui(self, backups_dir: str):
        self.title_lbl.setText(tr("settings.options_section"))
        self.backup_chk.setText(tr("settings.auto_backup"))
        self.adult_chk.setText(tr("settings.adult_content"))
        self.clear_cache_btn.setText(tr("settings.clear_cache"))
        self.cache_lbl.setText(tr("settings.backups_path", path=backups_dir or "-"))


class DatabaseCardWidget(QFrame):
    """Card widget for database maintenance, stats, and catalog purge."""

    def __init__(self, on_purge: Callable[[], None], parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsSection")
        self.setStyleSheet(create_section_frame().styleSheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        self.title_lbl = QLabel(tr("settings.db_section"))
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e8f0;")
        layout.addWidget(self.title_lbl)

        self.db_stats_lbl = QLabel(tr("settings.db_stats_loading"))
        self.db_stats_lbl.setStyleSheet("font-size: 13px; color: #94a3b8;")
        layout.addWidget(self.db_stats_lbl)

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
        self.purge_db_btn.clicked.connect(on_purge)
        db_actions_h.addWidget(self.purge_db_btn, stretch=1)
        layout.addLayout(db_actions_h)

    def retranslate_ui(self):
        self.title_lbl.setText(tr("settings.db_section"))
        self.db_desc_lbl.setText(tr("settings.db_purge_desc"))
        self.purge_db_btn.setText(tr("settings.purge_db_btn"))
