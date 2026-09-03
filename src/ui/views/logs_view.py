import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QPlainTextEdit,
    QApplication,
    QMessageBox,
)
from PySide6.QtGui import QTextCursor, QFont, QColor
from PySide6.QtCore import Qt

from src.utils.logger import log_emitter, qt_log_handler
from src.core.config import AppConfig

class LogsView(QWidget):
    """Modern real-time logs inspection view with filtering and 1-click clipboard copy."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_logs = []
        self.init_ui()
        self.load_initial_history()

        # Connect real-time Qt signal
        log_emitter.log_received.connect(self._on_log_received)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header bar
        header_layout = QHBoxLayout()
        title = QLabel("📋 Journaux d'Exécution & Logs")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #f8fafc;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Search filter
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filtrer les logs...")
        self.search_input.setFixedWidth(200)
        self.search_input.textChanged.connect(self._apply_filter)
        header_layout.addWidget(self.search_input)

        # Level combo
        self.level_combo = QComboBox()
        self.level_combo.addItems(["Tous les niveaux", "INFO", "WARNING", "ERROR", "DEBUG"])
        self.level_combo.currentIndexChanged.connect(self._apply_filter)
        header_layout.addWidget(self.level_combo)

        # Copy All Button
        self.copy_btn = QPushButton("📋 Copier Tout")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #6366f1; }
        """)
        self.copy_btn.clicked.connect(self.copy_all_logs)
        header_layout.addWidget(self.copy_btn)

        # Clear View Button
        self.clear_btn = QPushButton("🗑️ Effacer")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #202436;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #282e48; color: #f1f5f9; }
        """)
        self.clear_btn.clicked.connect(self.clear_logs)
        header_layout.addWidget(self.clear_btn)

        # Open Logs Folder Button
        self.open_logs_btn = QPushButton("📁 Dossier Logs")
        self.open_logs_btn.setStyleSheet("""
            QPushButton {
                background-color: #202436;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #282e48; }
        """)
        self.open_logs_btn.clicked.connect(self.open_logs_folder)
        header_layout.addWidget(self.open_logs_btn)

        layout.addLayout(header_layout)

        # Log Text Box
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0b0d14;
                color: #cbd5e1;
                border: 1px solid #1e2334;
                border-radius: 8px;
                padding: 12px;
                line-height: 1.4;
            }
        """)
        layout.addWidget(self.log_text)

        # Bottom info bar
        self.info_label = QLabel("Prêt. Les nouveaux événements s'affichent automatiquement ci-dessus.")
        self.info_label.setStyleSheet("font-size: 11px; color: #64748b;")
        layout.addWidget(self.info_label)

    def load_initial_history(self):
        """Loads buffered logs from QtLogHandler."""
        self.all_logs = list(qt_log_handler.history)
        self._apply_filter()

    def _on_log_received(self, msg: str, level: str):
        self.all_logs.append(msg)
        if len(self.all_logs) > qt_log_handler.max_history:
            self.all_logs.pop(0)

        if self._matches_filter(msg):
            self._append_formatted_line(msg)

    def _matches_filter(self, line: str) -> bool:
        search = self.search_input.text().strip().lower()
        if search and search not in line.lower():
            return False

        level_filter = self.level_combo.currentText()
        if level_filter != "Tous les niveaux":
            if f"[{level_filter}]" not in line:
                return False

        return True

    def _append_formatted_line(self, line: str):
        # Format HTML with colors
        if "[ERROR]" in line:
            color = "#f87171" # red
        elif "[WARNING]" in line:
            color = "#facc15" # yellow
        elif "[INFO]" in line:
            color = "#cbd5e1" # light gray
        elif "[DEBUG]" in line:
            color = "#38bdf8" # cyan
        else:
            color = "#94a3b8"

        html_line = f'<span style="color: {color};">{self._escape_html(line)}</span>'
        self.log_text.appendHtml(html_line)

        # Move cursor to end
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)

    def _escape_html(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _apply_filter(self):
        self.log_text.clear()
        for line in self.all_logs:
            if self._matches_filter(line):
                self._append_formatted_line(line)
        self.info_label.setText(f"{self.log_text.document().blockCount() - 1} message(s) affiché(s) sur {len(self.all_logs)} au total.")

    def copy_all_logs(self):
        text = self.log_text.toPlainText()
        if not text:
            QMessageBox.information(self, "Information", "Aucun log à copier.")
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.info_label.setText("✓ Tous les logs affichés ont été copiés dans le presse-papiers !")

    def clear_logs(self):
        self.log_text.clear()
        self.info_label.setText("Vue des logs effacée.")

    def open_logs_folder(self):
        log_dir = Path.home() / ".sims4_mod_manager" / "logs"
        if log_dir.exists():
            os.startfile(str(log_dir))
        else:
            QMessageBox.warning(self, "Erreur", "Le dossier des logs n'existe pas encore.")
