from typing import List
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
from PySide6.QtGui import QTextCursor, QFont

from src.api.client import get_api_client
from src.i18n import tr
from src.utils.logger import get_qt_log_handler, logger


class LogsView(QWidget):
    """Modern real-time logs inspection view with filtering and 1-click clipboard copy via API."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.all_logs: List[str] = []
        self.init_ui()
        self.load_initial_history()

        # Connect real-time Qt signal (handler attached in run.py before QApplication)
        qt_handler = get_qt_log_handler()
        if qt_handler:
            qt_handler._emitter.log_received.connect(self._on_log_received)

    def init_ui(self):
        """Exécute l'opération init ui."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header bar
        header_layout = QHBoxLayout()
        self.title_lbl = QLabel(tr("logs.title"))
        self.title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #f8fafc;")
        header_layout.addWidget(self.title_lbl)

        header_layout.addStretch()

        # Search filter
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("logs.search_placeholder"))
        self.search_input.setFixedWidth(200)
        self.search_input.textChanged.connect(self._apply_filter)
        header_layout.addWidget(self.search_input)

        # Level combo
        self.level_combo = QComboBox()
        self._populate_level_combo()
        self.level_combo.currentIndexChanged.connect(self._apply_filter)
        header_layout.addWidget(self.level_combo)

        # Copy All Button
        self.copy_btn = QPushButton(tr("logs.copy_btn"))
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
        self.clear_btn = QPushButton(tr("logs.clear_btn"))
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
        self.open_logs_btn = QPushButton(tr("logs.open_folder_btn"))
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
        """Loads logs through API /api/logs."""
        try:
            res = self.api_client.get_logs(limit=500)
            self.all_logs = res.get("items", [])
            self._apply_filter()
        except Exception as e:
            logger.error(f"Erreur API lors du chargement des logs: {e}")

    def _on_log_received(self, msg: str, level: str):
        self.all_logs.append(msg)
        if len(self.all_logs) > 1000:
            self.all_logs.pop(0)

        if self._matches_filter(msg):
            self._append_formatted_line(msg)

    def _matches_filter(self, line: str) -> bool:
        search = self.search_input.text().strip().lower()
        if search and search not in line.lower():
            return False

        level_filter = self.level_combo.currentData()
        if level_filter:
            if f"[{level_filter}]" not in line:
                return False

        return True

    def _append_formatted_line(self, line: str):
        if "[ERROR]" in line:
            color = "#f87171"
        elif "[WARNING]" in line:
            color = "#facc15"
        elif "[INFO]" in line:
            color = "#cbd5e1"
        elif "[DEBUG]" in line:
            color = "#38bdf8"
        else:
            color = "#94a3b8"

        html_line = f'<span style="color: {color};">{self._escape_html(line)}</span>'
        self.log_text.appendHtml(html_line)
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)

    def _escape_html(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _apply_filter(self):
        self.log_text.clear()
        for line in self.all_logs:
            if self._matches_filter(line):
                self._append_formatted_line(line)
        self.info_label.setText(f"{self.log_text.document().blockCount() - 1} / {len(self.all_logs)}")

    def copy_all_logs(self):
        """Exécute l'opération copy all logs."""
        text = self.log_text.toPlainText()
        if not text:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.info_label.setText(tr("logs.copy_success_msg"))

    def clear_logs(self):
        """Exécute l'opération clear logs."""
        try:
            self.api_client.clear_logs()
            self.all_logs.clear()
            self.log_text.clear()
            self.info_label.setText(tr("common.ready"))
        except Exception as e:
            QMessageBox.warning(self, tr("common.error"), f"{e}")

    def open_logs_folder(self):
        """Exécute l'opération open logs folder."""
        try:
            self.api_client.open_logs_folder()
        except Exception as e:
            QMessageBox.warning(self, tr("common.error"), f"{e}")

    def _populate_level_combo(self):
        current_data = self.level_combo.currentData()
        self.level_combo.blockSignals(True)
        self.level_combo.clear()
        self.level_combo.addItem(tr("logs.filter_all"), "")
        self.level_combo.addItem("INFO", "INFO")
        self.level_combo.addItem("WARNING", "WARNING")
        self.level_combo.addItem("ERROR", "ERROR")
        self.level_combo.addItem("DEBUG", "DEBUG")
        idx = self.level_combo.findData(current_data)
        if idx >= 0:
            self.level_combo.setCurrentIndex(idx)
        self.level_combo.blockSignals(False)

    def retranslate_ui(self):
        """Retranslates all text elements in LogsView."""
        self.title_lbl.setText(tr("logs.title"))
        self.search_input.setPlaceholderText(tr("logs.search_placeholder"))
        self.copy_btn.setText(tr("logs.copy_btn"))
        self.clear_btn.setText(tr("logs.clear_btn"))
        self.open_logs_btn.setText(tr("logs.open_folder_btn"))
        self._populate_level_combo()
        if not self.all_logs:
            self.info_label.setText(tr("common.ready"))
