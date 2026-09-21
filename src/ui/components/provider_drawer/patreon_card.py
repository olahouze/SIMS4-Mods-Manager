"""
PatreonDrawerCard: Encapsulates the Patreon provider status summary in the satellite drawer.
"""

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
)

from src.i18n import tr


class PatreonDrawerCard(QFrame):
    """Encapsulates the Patreon provider status summary in the satellite drawer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #13172e;
                border: 1px solid #222d52;
                border-radius: 8px;
                padding: 6px;
            }
        """)
        p_card_layout = QVBoxLayout(self)
        p_card_layout.setContentsMargins(8, 8, 8, 8)
        p_card_layout.setSpacing(4)

        p_header = QHBoxLayout()
        p_name = QLabel("Patreon")
        p_name.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        p_header.addWidget(p_name)
        p_header.addStretch()

        self.patreon_status_pill = QLabel(tr("drawer.status_ready"))
        self.patreon_status_pill.setStyleSheet("""
            background-color: #064e3b;
            color: #a7f3d0;
            border: 1px solid #059669;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 700;
        """)
        p_header.addWidget(self.patreon_status_pill)
        p_card_layout.addLayout(p_header)

        self.p_desc = QLabel(tr("drawer.patreon_desc"))
        self.p_desc.setStyleSheet("font-size: 10px; color: #64748b;")
        p_card_layout.addWidget(self.p_desc)

    def retranslate_ui(self):
        """Exécute l'opération retranslate ui."""
        self.p_desc.setText(tr("drawer.patreon_desc"))
        self.patreon_status_pill.setText(tr("drawer.status_ready"))
