import shutil
from pathlib import Path
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
from PySide6.QtCore import Qt

from src.core.config import AppConfig
from src.core.game_detector import GameDetector
from src.utils.logger import logger

class SettingsView(QWidget):
    """Settings page for paths, game launcher, backups, and preferences."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        title = QLabel("Paramètres de l'Application")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title)

        config = AppConfig.load()

        # 1. Sims 4 Mods Directory Section
        mods_frame = self._create_section_frame("Dossier des Mods Les Sims 4")
        m_layout = QVBoxLayout(mods_frame)

        detected_mods = GameDetector.detect_mods_dir(config.custom_mods_dir)
        mods_path_str = str(detected_mods) if detected_mods else ""

        path_h = QHBoxLayout()
        self.mods_path_input = QLineEdit(mods_path_str)
        path_h.addWidget(self.mods_path_input, stretch=3)

        browse_mods_btn = QPushButton("Parcourir...")
        browse_mods_btn.setStyleSheet("background-color: #202436; color: #f1f5f9; padding: 8px 14px; border-radius: 6px;")
        browse_mods_btn.clicked.connect(self.browse_mods_folder)
        path_h.addWidget(browse_mods_btn)

        m_layout.addLayout(path_h)

        status_lbl = QLabel("✓ Dossier détecté et valide" if (detected_mods and detected_mods.exists()) else "⚠️ Dossier non détecté")
        status_lbl.setStyleSheet("color: #34d399;" if (detected_mods and detected_mods.exists()) else "color: #f87171;")
        m_layout.addWidget(status_lbl)

        layout.addWidget(mods_frame)

        # 2. Game Executable & Launcher Section
        game_frame = self._create_section_frame("Exécutable du Jeu & Lanceur")
        g_layout = QVBoxLayout(game_frame)

        detected_exe = GameDetector.detect_game_executable(config.custom_game_exe)
        exe_path_str = str(detected_exe) if detected_exe else ""

        exe_h = QHBoxLayout()
        self.exe_path_input = QLineEdit(exe_path_str)
        exe_h.addWidget(self.exe_path_input, stretch=3)

        browse_exe_btn = QPushButton("Parcourir...")
        browse_exe_btn.setStyleSheet("background-color: #202436; color: #f1f5f9; padding: 8px 14px; border-radius: 6px;")
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

        self.backup_chk = QCheckBox("Créer automatiquement une sauvegarde (.zip) de l'ancienne version avant mise à jour")
        self.backup_chk.setChecked(config.auto_backup)
        p_layout.addWidget(self.backup_chk)

        self.adult_chk = QCheckBox("Activer les contenus adultes / NSFW (+18 ans) sur LoversLab")
        self.adult_chk.setChecked(config.adult_content_enabled)
        p_layout.addWidget(self.adult_chk)

        # Cache clear button
        cache_h = QHBoxLayout()
        cache_lbl = QLabel(f"Emplacement des sauvegardes : {AppConfig.get_backups_dir()}")
        cache_lbl.setStyleSheet("font-size: 11px; color: #64748b;")
        cache_h.addWidget(cache_lbl)
        cache_h.addStretch()

        clear_cache_btn = QPushButton("🗑️ Vider le cache des miniatures")
        clear_cache_btn.setStyleSheet("background-color: #202436; color: #94a3b8; padding: 6px 12px; border-radius: 6px;")
        clear_cache_btn.clicked.connect(self.clear_cache)
        cache_h.addWidget(clear_cache_btn)

        p_layout.addLayout(cache_h)
        layout.addWidget(pref_frame)

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

    def browse_mods_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier Mods de Sims 4")
        if dir_path:
            self.mods_path_input.setText(dir_path)

    def browse_game_exe(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner l'exécutable Sims 4", "", "Exécutables (*.exe)"
        )
        if file_path:
            self.exe_path_input.setText(file_path)

    def launch_game(self):
        exe = self.exe_path_input.text().strip()
        exe_path = Path(exe) if exe else None
        ok = GameDetector.launch_game(exe_path)
        if not ok:
            QMessageBox.warning(self, "Erreur", "Impossible de lancer le jeu Les Sims 4. Vérifiez le chemin de l'exécutable.")

    def clear_cache(self):
        cache_dir = AppConfig.get_thumbnails_cache_dir()
        count = 0
        for f in cache_dir.glob("*"):
            try:
                f.unlink()
                count += 1
            except Exception:
                pass
        QMessageBox.information(self, "Cache Vidé", f"{count} miniatures supprimées du cache.")

    def save_settings(self):
        config = AppConfig.load()
        config.custom_mods_dir = self.mods_path_input.text().strip() or None
        config.custom_game_exe = self.exe_path_input.text().strip() or None
        config.auto_backup = self.backup_chk.isChecked()
        config.adult_content_enabled = self.adult_chk.isChecked()
        config.save()
        QMessageBox.information(self, "Succès", "Paramètres enregistrés avec succès !")
