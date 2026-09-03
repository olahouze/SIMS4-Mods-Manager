from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
)
from PySide6.QtCore import Qt

class ProgressDialog(QDialog):
    """A clean dark mode dialog showing asynchronous task progress."""

    def __init__(self, title: str = "Opération en cours...", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 160)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.status_label = QLabel("Veuillez patienter...")
        self.status_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #f8fafc;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.details_label = QLabel("")
        self.details_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
        layout.addWidget(self.details_label)

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_details(self, text: str):
        self.details_label.setText(text)

    def set_progress(self, value: int):
        self.progress_bar.setValue(value)

    def set_indeterminate(self, is_indeterminate: bool):
        if is_indeterminate:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
