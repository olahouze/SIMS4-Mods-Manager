from typing import List, Dict, Any, Union
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QLabel,
)
from src.i18n import tr


class DependenciesSummaryWidget(QFrame):
    """
    Reusable widget displaying a concise summary of mod dependencies:
    Official Game DLC badges, Installed/Detected pills, and '+ X other(s)...' label.
    Shared across ModCard, InstalledCard, and ModDetailView.
    """

    def __init__(self, dependencies: List[Union[Dict[str, Any], Any]], max_show: int = 2, parent=None):
        super().__init__(parent)
        self.dependencies = dependencies or []
        self.max_show = max_show

        self._init_ui()

    def _init_ui(self):
        if not self.dependencies:
            self.setVisible(False)
            return

        self.setStyleSheet("""
            QFrame {
                background-color: #0b0e1a;
                border: 1px solid #1a2035;
                border-radius: 6px;
                padding: 3px 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        header_lbl = QLabel(tr("catalog.req_header", count=len(self.dependencies)))
        header_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #94a3b8;")
        layout.addWidget(header_lbl)

        for dep in self.dependencies[: self.max_show]:
            d_title = dep.get("title") if isinstance(dep, dict) else getattr(dep, "title", "Mod")
            d_status = (
                dep.get("status") if isinstance(dep, dict) else getattr(dep, "status", "DETECTED_NOT_INSTALLED")
            )
            is_inst = dep.get("is_installed") if isinstance(dep, dict) else getattr(dep, "is_installed", False)
            is_dlc = dep.get("is_game_dlc") if isinstance(dep, dict) else getattr(dep, "is_game_dlc", False)

            if is_dlc or d_status == "GAME_DLC":
                pill_text = f"🎮 {d_title} (DLC Sims 4)"
                pill_style = "background-color: #3b0764; color: #d8b4fe; border: 1px solid #7e22ce;"
            elif is_inst or d_status == "INSTALLED":
                pill_text = f"🟢 {d_title} (Installé)"
                pill_style = "background-color: #064e3b; color: #a7f3d0; border: 1px solid #059669;"
            elif d_status == "DETECTED_NOT_INSTALLED":
                pill_text = f"🔵 {d_title} (Détecté)"
                pill_style = "background-color: #1e3a8a; color: #93c5fd; border: 1px solid #2563eb;"
            elif d_status == "NOT_DETECTED_SCANNING":
                pill_text = f"🟡 {d_title} (Scan en cours)"
                pill_style = "background-color: #451a03; color: #fde68a; border: 1px solid #d97706;"
            else:
                pill_text = f"⚪ {d_title} (Non détecté)"
                pill_style = "background-color: #27272a; color: #d4d4d8; border: 1px solid #52525b;"

            pill = QLabel(pill_text)
            pill.setStyleSheet(f"""
                font-size: 9px;
                font-weight: 600;
                border-radius: 4px;
                padding: 1px 4px;
                {pill_style}
            """)
            pill.setToolTip(f"Dépendance: {d_title}\nStatut: {pill_text}")
            layout.addWidget(pill)

        if len(self.dependencies) > self.max_show:
            extra_count = len(self.dependencies) - self.max_show
            more_lbl = QLabel(tr("catalog.more_deps", count=extra_count))
            more_lbl.setStyleSheet("font-size: 9px; color: #64748b; font-style: italic;")
            full_tooltip = "Dépendances complètes :\n" + "\n".join(
                f"• {d.get('title') if isinstance(d, dict) else (d.title if hasattr(d, 'title') else str(d))}"
                for d in self.dependencies
            )
            more_lbl.setToolTip(full_tooltip)
            layout.addWidget(more_lbl)
