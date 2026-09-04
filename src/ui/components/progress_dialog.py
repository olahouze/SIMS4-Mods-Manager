from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)


class ProgressDialog(QDialog):
    """A premium dark-themed dialog displaying real-time download speed, percentage, and unzip status."""

    def __init__(self, title: str = "Opération en cours...", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(500, 190)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.init_ui(title)

    def init_ui(self, title: str):
        self.setStyleSheet("""
            QDialog {
                background-color: #0f121e;
                border: 1px solid #232b42;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        # Header Title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #f8fafc;")
        header_layout.addWidget(self.title_label, stretch=1)

        self.pct_badge = QLabel("0%")
        self.pct_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #38bdf8;
            border: 1px solid #0284c7;
            border-radius: 10px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 700;
        """)
        header_layout.addWidget(self.pct_badge)
        layout.addLayout(header_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #131726;
                border: 1px solid #232d45;
                border-radius: 6px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #6366f1);
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Divider line
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #1e2538;")
        layout.addWidget(divider)

        # Status Label (Action name: e.g. "Téléchargement en cours...", "Décompression...")
        self.status_label = QLabel("Initialisation...")
        self.status_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #cbd5e1;")
        layout.addWidget(self.status_label)

        # Details Label (Metrics: e.g. "12.4 / 45.0 Mo • 3.2 Mo/s" or "Décompression : 8 fichiers...")
        self.details_label = QLabel("Connexion au serveur...")
        self.details_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
        layout.addWidget(self.details_label)

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_details(self, text: str):
        self.details_label.setText(text)

    def set_progress(self, value: int):
        val = max(0, min(100, value))
        self.progress_bar.setValue(val)
        self.pct_badge.setText(f"{val}%")

    def update_progress(self, percent: int, status: str, details: str = ""):
        self.set_progress(percent)
        if status:
            self.set_status(status)
        if details:
            self.set_details(details)

    def set_indeterminate(self, is_indeterminate: bool):
        if is_indeterminate:
            self.progress_bar.setRange(0, 0)
            self.pct_badge.setText("...")
        else:
            self.progress_bar.setRange(0, 100)
            self.pct_badge.setText(f"{self.progress_bar.value()}%")
