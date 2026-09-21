"""
SubcategoryRowWidget: Progress row for a single LoversLab / provider subcategory
in the ProviderDrawer.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
from PySide6.QtCore import Qt


class SubcategoryRowWidget(QFrame):
    """Row widget representing a single subcategory progress in the provider drawer."""

    def __init__(self, cat_id: str, name: str, icon: str, parent=None):
        super().__init__(parent)
        self.cat_id = cat_id
        self.name = name
        self.icon = icon

        self.setStyleSheet("""
            QFrame {
                background-color: #0e1224;
                border: 1px solid #161e38;
                border-radius: 4px;
                padding: 2px 4px;
            }
        """)
        r_layout = QHBoxLayout(self)
        r_layout.setContentsMargins(4, 2, 4, 2)
        r_layout.setSpacing(6)

        self.lbl_icon = QLabel(icon)
        self.lbl_icon.setFixedWidth(16)
        r_layout.addWidget(self.lbl_icon)

        self.lbl_name = QLabel(name)
        self.lbl_name.setStyleSheet("font-size: 10px; color: #cbd5e1; font-weight: 500;")
        r_layout.addWidget(self.lbl_name, stretch=1)

        self.lbl_detail = QLabel("Attente")
        self.lbl_detail.setStyleSheet("font-size: 9px; color: #64748b;")
        self.lbl_detail.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        r_layout.addWidget(self.lbl_detail)

    def set_status(self, text: str, color: str = "#64748b"):
        """Exécute l'opération set status.

        Args:
            text: Paramètre text.
            color: Paramètre color.
        """
        self.lbl_detail.setText(text)
        weight = "700" if color != "#64748b" else "400"
        self.lbl_detail.setStyleSheet(f"font-size: 9px; color: {color}; font-weight: {weight};")

    @property
    def labels_tuple(self):
        """Compatibility tuple (lbl_icon, lbl_name, lbl_detail)."""
        return self.lbl_icon, self.lbl_name, self.lbl_detail
