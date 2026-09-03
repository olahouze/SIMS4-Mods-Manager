from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import Signal, Qt

class FilterBar(QWidget):
    """Modern filter bar with search, multi-criteria selectors and sync button."""

    filters_changed = Signal()
    sync_requested = Signal(int) # emits number of pages to sync

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(10)

        # Search field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher un mod, un auteur, un tag...")
        self.search_input.textChanged.connect(self.filters_changed.emit)
        layout.addWidget(self.search_input, stretch=2)

        # Source Combo
        self.source_combo = QComboBox()
        self.source_combo.addItems(["Toutes les sources", "LoversLab", "Patreon"])
        self.source_combo.currentIndexChanged.connect(self.filters_changed.emit)
        layout.addWidget(self.source_combo)

        # Access Combo
        self.access_combo = QComboBox()
        self.access_combo.addItems([
            "Tous les accès",
            "🔓 Public / Gratuit",
            "✅ Débloqué (Abonné)",
            "🔒 Verrouillé Patreon",
        ])
        self.access_combo.currentIndexChanged.connect(self.filters_changed.emit)
        layout.addWidget(self.access_combo)

        # Install Status Combo
        self.status_combo = QComboBox()
        self.status_combo.addItems([
            "Tous les états",
            "Non installés",
            "Déjà installés",
            "Mises à jour disponibles",
        ])
        self.status_combo.currentIndexChanged.connect(self.filters_changed.emit)
        layout.addWidget(self.status_combo)

        # Sort Combo
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Date de màj (Récent)",
            "Titre (A-Z)",
        ])
        self.sort_combo.currentIndexChanged.connect(self.filters_changed.emit)
        layout.addWidget(self.sort_combo)

        # Pages to sync Combo
        self.pages_combo = QComboBox()
        self.pages_combo.addItems(["1 page", "2 pages", "5 pages", "10 pages", "20 pages"])
        self.pages_combo.setCurrentText("5 pages")
        self.pages_combo.setToolTip("Nombre de pages à parcourir lors de la synchronisation")
        self.pages_combo.setFixedWidth(105)
        layout.addWidget(self.pages_combo)

        # Sync Button
        self.sync_btn = QPushButton("🔄 Synchroniser")
        self.sync_btn.setProperty("class", "PrimaryBtn")
        self.sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #6366f1;
            }
        """)
        self.sync_btn.clicked.connect(self._on_sync_clicked)
        layout.addWidget(self.sync_btn)

    def _on_sync_clicked(self):
        text = self.pages_combo.currentText()
        count = int(text.split()[0])
        self.sync_requested.emit(count)

    def get_filter_state(self) -> dict:
        """Returns the current filter parameters as a dict."""
        return {
            "search": self.search_input.text().strip().lower(),
            "source": self.source_combo.currentText(),
            "access": self.access_combo.currentText(),
            "status": self.status_combo.currentText(),
            "sort": self.sort_combo.currentText(),
        }
