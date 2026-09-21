"""
Interactive row widget representing a module item in ReportPreviewDialog
with a selection checkbox and radio buttons to mark as missing mod or comment/not a mod.
"""

from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
)
from PySide6.QtCore import Qt, Signal

from src.i18n import tr


class ReportModuleRowWidget(QFrame):
    """Row widget for a detected requirement in ReportPreviewDialog."""

    selection_changed = Signal()
    override_changed = Signal(str, str)  # (mod_name, "MOD" | "COMMENT")

    def __init__(self, mod_name: str, is_missing_default: bool = True, parent=None):
        super().__init__(parent)
        self.mod_name = mod_name
        self.is_missing_default = is_missing_default
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #121829;
                border: 1px solid #2e3856;
                border-radius: 6px;
                padding: 4px 8px;
            }
        """)
        r_layout = QVBoxLayout(self)
        r_layout.setContentsMargins(6, 6, 6, 6)
        r_layout.setSpacing(4)

        top_row = QHBoxLayout()
        self.cb = QCheckBox(self.mod_name)
        self.cb.setChecked(True)
        self.cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cb.setStyleSheet("""
            QCheckBox {
                color: #f1f5f9;
                font-size: 12px;
                font-weight: 700;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #6366f1;
                background-color: #0b0e1a;
            }
            QCheckBox::indicator:hover { border-color: #818cf8; }
            QCheckBox::indicator:checked { background-color: #4f46e5; border-color: #6366f1; }
        """)
        top_row.addWidget(self.cb)
        top_row.addStretch()
        r_layout.addLayout(top_row)

        choice_layout = QHBoxLayout()
        choice_layout.setContentsMargins(24, 0, 0, 2)
        choice_layout.setSpacing(16)

        self.btn_group = QButtonGroup(self)
        self.rb_missing = QRadioButton(tr("report_dialog.choice_missing_mod"))
        self.rb_missing.setChecked(self.is_missing_default)
        self.rb_missing.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rb_missing.setStyleSheet("""
            QRadioButton {
                color: #93c5fd;
                font-size: 11px;
                font-weight: 600;
                spacing: 6px;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
                border-radius: 7px;
                border: 1px solid #60a5fa;
                background-color: #0f172a;
            }
            QRadioButton::indicator:checked {
                background-color: #3b82f6;
                border: 3px solid #0f172a;
            }
        """)

        self.rb_unnecessary = QRadioButton(tr("report_dialog.choice_not_a_mod"))
        self.rb_unnecessary.setChecked(not self.is_missing_default)
        self.rb_unnecessary.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rb_unnecessary.setStyleSheet("""
            QRadioButton {
                color: #fda4af;
                font-size: 11px;
                font-weight: 600;
                spacing: 6px;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
                border-radius: 7px;
                border: 1px solid #f43f5e;
                background-color: #0f172a;
            }
            QRadioButton::indicator:checked {
                background-color: #f43f5e;
                border: 3px solid #0f172a;
            }
        """)

        self.btn_group.addButton(self.rb_missing, 0)
        self.btn_group.addButton(self.rb_unnecessary, 1)

        choice_layout.addWidget(self.rb_missing)
        choice_layout.addWidget(self.rb_unnecessary)
        choice_layout.addStretch()
        r_layout.addLayout(choice_layout)

        self.cb.stateChanged.connect(self._on_cb_toggled)
        self.rb_missing.toggled.connect(self._on_rb_missing_toggled)
        self.rb_unnecessary.toggled.connect(self._on_rb_unnecessary_toggled)

    def _on_cb_toggled(self):
        self.rb_missing.setEnabled(self.cb.isChecked())
        self.rb_unnecessary.setEnabled(self.cb.isChecked())
        self.selection_changed.emit()

    def _on_rb_missing_toggled(self, checked: bool):
        if checked:
            self.override_changed.emit(self.mod_name, "MOD")
        self.selection_changed.emit()

    def _on_rb_unnecessary_toggled(self, checked: bool):
        if checked:
            self.override_changed.emit(self.mod_name, "COMMENT")
        self.selection_changed.emit()

    @property
    def is_selected(self) -> bool:
        """Exécute l'opération is selected.

        Returns:
            Résultat de l'opération is_selected.
        """
        return self.cb.isChecked()

    @property
    def is_missing_mod(self) -> bool:
        """Exécute l'opération is missing mod.

        Returns:
            Résultat de l'opération is_missing_mod.
        """
        return self.rb_missing.isChecked()
