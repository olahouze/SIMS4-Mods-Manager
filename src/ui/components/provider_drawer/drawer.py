"""
ProviderDrawer: Modular retractable right-side satellite drawer for provider status,
subcategory progress monitoring, and individual site scraping controls.
"""

from typing import Dict, Any, Tuple, Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal

from src.i18n import tr
from src.ui.components.provider_drawer.drawer_styles import DrawerStyles
from src.ui.components.provider_drawer.subcategory_row import SubcategoryRowWidget
from src.ui.components.provider_drawer.provider_cards import LoversLabDrawerCard, PatreonDrawerCard


class ProviderDrawer(QWidget):
    """
    Modular retractable right-side satellite drawer for provider status,
    subcategory progress monitoring, and individual site scraping controls (Pause, Resume, Stop, Resync).
    """

    start_requested = Signal(str)  # provider name
    pause_requested = Signal(str)  # provider name
    resume_requested = Signal(str)  # provider name
    stop_requested = Signal(str)  # provider name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_status: Optional[Dict[str, Any]] = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 1. Persistent Edge Tab (Always visible on right edge)
        self.tab_widget = QFrame()
        self.tab_widget.setFixedWidth(130)
        self.tab_widget.setStyleSheet("""
            QFrame {
                background-color: #0c1020;
                border: 1px solid #1e2844;
                border-radius: 10px;
                padding: 4px;
            }
        """)
        tab_layout = QVBoxLayout(self.tab_widget)
        tab_layout.setContentsMargins(4, 6, 4, 6)
        tab_layout.setSpacing(6)

        self.btn_toggle_drawer = QPushButton(tr("drawer.btn_toggle_collapsed"))
        self.btn_toggle_drawer.setFixedHeight(32)
        self.btn_toggle_drawer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_drawer.setToolTip(tr("drawer.btn_toggle_tip"))
        self.btn_toggle_drawer.clicked.connect(self.toggle_drawer)
        self._style_toggle_button("OK")
        tab_layout.addWidget(self.btn_toggle_drawer)

        # Site status badge for LoversLab (on collapsed edge)
        self.tab_loverslab_pill = QLabel("LoversLab 🟢")
        self.tab_loverslab_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tab_loverslab_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_loverslab_pill.setToolTip(tr("drawer.pill_tip_ll"))
        self.tab_loverslab_pill.mousePressEvent = lambda e: self.toggle_drawer()
        self._style_site_tab_pill(self.tab_loverslab_pill, "OK", "LoversLab 🟢")
        tab_layout.addWidget(self.tab_loverslab_pill)

        # Future provider badge (Patreon)
        self.tab_patreon_pill = QLabel("Patreon 🟢")
        self.tab_patreon_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tab_patreon_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_patreon_pill.setToolTip(tr("drawer.pill_tip_patreon"))
        self.tab_patreon_pill.mousePressEvent = lambda e: self.toggle_drawer()
        self._style_site_tab_pill(self.tab_patreon_pill, "OK", "Patreon 🟢")
        tab_layout.addWidget(self.tab_patreon_pill)

        tab_layout.addStretch()
        main_layout.addWidget(self.tab_widget)

        # 2. Retractable Drawer Panel
        self.drawer_panel = QFrame()
        self.drawer_panel.setObjectName("DrawerPanel")
        self.drawer_panel.setFixedWidth(350)
        self.drawer_panel.setVisible(False)
        self.drawer_panel.setStyleSheet("""
            QFrame#DrawerPanel {
                background-color: #0e1224;
                border: 1px solid #1e2844;
                border-radius: 12px;
            }
        """)
        d_layout = QVBoxLayout(self.drawer_panel)
        d_layout.setContentsMargins(12, 12, 12, 12)
        d_layout.setSpacing(10)

        # Drawer Header
        d_header = QHBoxLayout()
        self.d_title = QLabel(tr("drawer.title"))
        self.d_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #f8fafc;")
        d_header.addWidget(self.d_title)
        d_header.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                border: none;
                font-weight: 700;
                font-size: 14px;
            }
            QPushButton:hover { color: #f8fafc; }
        """)
        btn_close.clicked.connect(self.toggle_drawer)
        d_header.addWidget(btn_close)
        d_layout.addLayout(d_header)

        # Scrollable container for provider cards
        drawer_scroll = QScrollArea()
        drawer_scroll.setWidgetResizable(True)
        drawer_scroll.setStyleSheet("background-color: transparent; border: none;")

        providers_container = QWidget()
        providers_layout = QVBoxLayout(providers_container)
        providers_layout.setContentsMargins(0, 0, 0, 0)
        providers_layout.setSpacing(10)

        # --- LoversLab Provider Card ---
        self.ll_card = LoversLabDrawerCard(self)
        self.ll_card.start_requested.connect(self.start_requested.emit)
        self.ll_card.pause_requested.connect(self.pause_requested.emit)
        self.ll_card.resume_requested.connect(self.resume_requested.emit)
        self.ll_card.stop_requested.connect(self.stop_requested.emit)
        providers_layout.addWidget(self.ll_card)

        # --- Patreon Card ---
        self.patreon_card = PatreonDrawerCard(self)
        providers_layout.addWidget(self.patreon_card)

        providers_layout.addStretch()
        drawer_scroll.setWidget(providers_container)
        d_layout.addWidget(drawer_scroll)

        main_layout.addWidget(self.drawer_panel)

    # Backward compatible attributes delegated to LoversLab card
    @property
    def subcat_widgets(self) -> Dict[str, SubcategoryRowWidget]:
        return self.ll_card.subcat_widgets

    @property
    def subcat_rows(self) -> Dict[str, Tuple[QLabel, QLabel, QLabel]]:
        return self.ll_card.subcat_rows

    @property
    def drawer_status_pill(self) -> QLabel:
        return self.ll_card.drawer_status_pill

    @property
    def drawer_progress_bar(self):
        return self.ll_card.drawer_progress_bar

    @property
    def btn_resync(self) -> QPushButton:
        return self.ll_card.btn_resync

    @property
    def btn_pause_resume(self) -> QPushButton:
        return self.ll_card.btn_pause_resume

    @property
    def btn_stop(self) -> QPushButton:
        return self.ll_card.btn_stop

    def toggle_drawer(self):
        """Toggles visibility of the drawer panel."""
        new_vis = not self.drawer_panel.isVisible()
        self.drawer_panel.setVisible(new_vis)
        arrow = "▶" if new_vis else "◀"
        cur_t = self.btn_toggle_drawer.text()
        parts = cur_t.rsplit(" ", 1)
        base = parts[0] if len(parts) > 1 else cur_t
        self.btn_toggle_drawer.setText(f"{base} {arrow}")

    def update_sync_status(self, status: Dict[str, Any]):
        """Updates drawer status, progress bar, action buttons, and persistent tab."""
        self._last_status = status
        is_running = status.get("is_running", False)
        is_paused = status.get("is_paused", False)
        pct = status.get("progress_percent", 0)
        has_error = status.get("has_error", False)

        arrow = "▶" if self.drawer_panel.isVisible() else "◀"

        # 1. Update Persistent Tab
        if has_error:
            self.btn_toggle_drawer.setText(f"🔴 Sites {arrow}")
            self._style_toggle_button("ERROR")
            self._style_site_tab_pill(self.tab_loverslab_pill, "ERROR", "LoversLab 🔴")
        elif is_paused:
            self.btn_toggle_drawer.setText(f"⏸️ Sites ({pct}%) {arrow}")
            self._style_toggle_button("PAUSED")
            self._style_site_tab_pill(self.tab_loverslab_pill, "PAUSED", f"LoversLab ⏸️ {pct}%")
        elif is_running:
            self.btn_toggle_drawer.setText(f"🔵 Sites ({pct}%) {arrow}")
            self._style_toggle_button("RUNNING")
            self._style_site_tab_pill(self.tab_loverslab_pill, "RUNNING", f"LoversLab 🔵 {pct}%")
        else:
            self.btn_toggle_drawer.setText(f"🛰️ Sites {arrow}")
            self._style_toggle_button("OK")
            self._style_site_tab_pill(self.tab_loverslab_pill, "OK", "LoversLab 🟢")

        # 2. Delegate LoversLab details to the card
        self.ll_card.update_status(status)

    def retranslate_ui(self):
        """Retranslates all static and dynamic UI texts according to current language."""
        self.d_title.setText(tr("drawer.title"))
        self.btn_toggle_drawer.setToolTip(tr("drawer.btn_toggle_tip"))
        self.tab_loverslab_pill.setToolTip(tr("drawer.pill_tip_ll"))
        self.tab_patreon_pill.setToolTip(tr("drawer.pill_tip_patreon"))
        self.ll_card.retranslate_ui()
        self.patreon_card.retranslate_ui()

        if self._last_status:
            self.update_sync_status(self._last_status)
        else:
            arrow = "▶" if self.drawer_panel.isVisible() else "◀"
            self.btn_toggle_drawer.setText(f"🛰️ Sites {arrow}")

    def _style_toggle_button(self, state: str):
        if getattr(self, "_last_toggle_btn_state", None) == state:
            return
        self._last_toggle_btn_state = state
        self.btn_toggle_drawer.setStyleSheet(DrawerStyles.toggle_button(state))

    def _style_site_tab_pill(self, label: QLabel, state: str, text: str):
        label.setText(text)
        if not hasattr(self, "_last_tab_states"):
            self._last_tab_states = {}
        if self._last_tab_states.get(label) == state:
            return
        self._last_tab_states[label] = state
        label.setStyleSheet(DrawerStyles.site_tab_pill(state))
