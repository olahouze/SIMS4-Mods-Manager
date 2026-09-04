from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
)
from PySide6.QtCore import Signal


class FilterBar(QWidget):
    """Modern filter bar with search and multi-criteria selectors."""

    filters_changed = Signal()

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
        self.search_input.textChanged.connect(self._on_control_changed)
        layout.addWidget(self.search_input, stretch=2)

        # Source Combo
        self.source_combo = QComboBox()
        self.source_combo.addItems(["Toutes les sources", "LoversLab", "Patreon"])
        self.source_combo.currentIndexChanged.connect(self._on_control_changed)
        layout.addWidget(self.source_combo)

        # Access / State Combo (État du mod)
        self.access_combo = QComboBox()
        self.access_combo.addItems(
            [
                "Tous les états",
                "🌐 Directement sur le site",
                "🔑 Nécessite une connexion (compte)",
                "⭐ Nécessite un abonnement",
                "✅ Débloqué (Abonné)",
            ]
        )
        self.access_combo.setToolTip("Filtrer par disponibilité (direct sur le site, compte requis, abonnement Patreon...)")
        self.access_combo.currentIndexChanged.connect(self._on_control_changed)
        layout.addWidget(self.access_combo)

        # Install Status Combo (Statut d'installation)
        self.status_combo = QComboBox()
        self.status_combo.addItems(
            [
                "Toutes les installations",
                "Non installés",
                "Déjà installés",
                "Mises à jour disponibles",
            ]
        )
        self.status_combo.setToolTip("Filtrer par statut d'installation dans Les Sims 4")
        self.status_combo.currentIndexChanged.connect(self._on_control_changed)
        layout.addWidget(self.status_combo)

        # Sort Combo
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            [
                "Date de màj (Récent)",
                "Titre (A-Z)",
            ]
        )
        self.sort_combo.currentIndexChanged.connect(self._on_control_changed)
        layout.addWidget(self.sort_combo)

    def _on_control_changed(self, *args):
        """Emits filters_changed regardless of any arguments passed by widget signals."""
        self.filters_changed.emit()

    def get_filter_state(self) -> dict:
        """Returns the current filter parameters as a dict."""
        return {
            "search": self.search_input.text().strip().lower(),
            "source": self.source_combo.currentText(),
            "access": self.access_combo.currentText(),
            "status": self.status_combo.currentText(),
            "sort": self.sort_combo.currentText(),
        }
