"""Composant de base pour les fenêtres modales PySide6 avec thème sombre et centrage."""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)


class BaseModalDialog(QDialog):
    """Boîte de dialogue modale stylisée avec thème sombre, centrage et gestion de la fermeture."""

    DEFAULT_STYLE = """
        QDialog {
            background-color: #0f121e;
            border: 1px solid #232b42;
            border-radius: 12px;
        }
    """

    def __init__(
        self,
        title: str = "",
        width: int = 500,
        height: int = 300,
        parent: Optional[QWidget] = None,
        closable: bool = True,
    ) -> None:
        """Initialise la boîte de dialogue modale.

        Args:
            title: Titre de la fenêtre.
            width: Largeur initiale en pixels.
            height: Hauteur initiale en pixels.
            parent: Widget parent éventuel.
            closable: Si True, affiche une croix de fermeture en haut à droite.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(width, height)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.setStyleSheet(self.DEFAULT_STYLE)
        self._closable = closable
        self._center_on_parent(parent)

    def _center_on_parent(self, parent: Optional[QWidget]) -> None:
        """Centre la boîte de dialogue par rapport à la fenêtre parente ou à l'écran."""
        if parent:
            geo = parent.geometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(max(0, x), max(0, y))

    def create_header(self, title: str, subtitle: Optional[str] = None) -> QHBoxLayout:
        """Crée un bandeau d'en-tête standardisé avec titre et bouton de fermeture optionnel.

        Args:
            title: Libellé du titre principal.
            subtitle: Sous-titre explicatif optionnel.

        Returns:
            Le layout horizontal d'en-tête configuré.
        """
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc;")
        text_layout.addWidget(title_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
            text_layout.addWidget(sub_label)

        header_layout.addLayout(text_layout, stretch=1)

        if self._closable:
            close_btn = QPushButton("✕")
            close_btn.setFixedSize(28, 28)
            close_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #94a3b8;
                    font-size: 14px;
                    border: none;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #1e293b;
                    color: #f8fafc;
                }
            """)
            close_btn.clicked.connect(self.reject)
            header_layout.addWidget(close_btn)

        return header_layout

    def keyPressEvent(self, event) -> None:
        """Permet la fermeture immédiate sur appui de la touche Échap."""
        if event.key() == Qt.Key.Key_Escape and self._closable:
            self.reject()
        else:
            super().keyPressEvent(event)
