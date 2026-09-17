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
    QProgressBar,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal

from src.i18n import tr
from src.ui.components.provider_drawer.drawer_styles import DrawerStyles
from src.ui.components.provider_drawer.subcategory_row import SubcategoryRowWidget


class ProviderDrawer(QWidget):
    """
    Modular retractable right-side satellite drawer for provider status,
    subcategory progress monitoring, and individual site scraping controls (Pause, Resume, Stop, Resync).
    """

    start_requested = Signal(str)   # provider name
    pause_requested = Signal(str)   # provider name
    resume_requested = Signal(str)  # provider name
    stop_requested = Signal(str)    # provider name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ll_is_expanded = True
        self._last_status: Optional[Dict[str, Any]] = None
        self.subcat_widgets: Dict[str, SubcategoryRowWidget] = {}
        self.subcat_rows: Dict[str, Tuple[QLabel, QLabel, QLabel]] = {}

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
        ll_card = QFrame()
        ll_card.setStyleSheet("""
            QFrame {
                background-color: #13172e;
                border: 1px solid #222d52;
                border-radius: 8px;
                padding: 4px;
            }
        """)
        ll_layout = QVBoxLayout(ll_card)
        ll_layout.setContentsMargins(8, 8, 8, 8)
        ll_layout.setSpacing(8)

        # Header
        ll_header = QHBoxLayout()
        ll_name = QLabel("LoversLab")
        ll_name.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        ll_header.addWidget(ll_name)
        ll_header.addStretch()

        self.drawer_status_pill = QLabel(tr("drawer.status_ready"))
        self._style_status_pill("OK", tr("drawer.status_ready"))
        ll_header.addWidget(self.drawer_status_pill)

        self.btn_collapse_ll = QPushButton("▼")
        self.btn_collapse_ll.setFixedSize(20, 20)
        self.btn_collapse_ll.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_collapse_ll.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                border: none;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover { color: #f8fafc; }
        """)
        self.btn_collapse_ll.clicked.connect(self._toggle_loverslab_section)
        ll_header.addWidget(self.btn_collapse_ll)
        ll_layout.addLayout(ll_header)

        # Collapsed Summary
        self.ll_collapsed_summary = QWidget()
        cs_layout = QVBoxLayout(self.ll_collapsed_summary)
        cs_layout.setContentsMargins(0, 2, 0, 2)
        cs_layout.setSpacing(4)
        self.ll_collapsed_summary_lbl = QLabel(tr("drawer.summary", count=0))
        self.ll_collapsed_summary_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        cs_layout.addWidget(self.ll_collapsed_summary_lbl)
        self.ll_collapsed_summary.setVisible(False)
        ll_layout.addWidget(self.ll_collapsed_summary)

        # Expanded Details
        self.ll_expanded_details = QWidget()
        ed_layout = QVBoxLayout(self.ll_expanded_details)
        ed_layout.setContentsMargins(0, 0, 0, 0)
        ed_layout.setSpacing(8)

        self.drawer_progress_bar = QProgressBar()
        self.drawer_progress_bar.setFixedHeight(8)
        self.drawer_progress_bar.setRange(0, 100)
        self.drawer_progress_bar.setValue(0)
        self.drawer_progress_bar.setTextVisible(False)
        self.drawer_progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0a0e1c;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 4px;
            }
        """)
        ed_layout.addWidget(self.drawer_progress_bar)

        self.drawer_lbl_progress = QLabel(tr("drawer.progress", done=0, total=0, pct=0))
        self.drawer_lbl_progress.setStyleSheet("font-size: 11px; color: #cbd5e1; font-weight: 600;")
        ed_layout.addWidget(self.drawer_lbl_progress)

        self.drawer_lbl_category = QLabel(tr("drawer.category_current", cat=tr("common.ready")))
        self.drawer_lbl_category.setStyleSheet("font-size: 11px; color: #94a3b8;")
        ed_layout.addWidget(self.drawer_lbl_category)

        self.drawer_lbl_mods = QLabel(tr("drawer.mods_count", count=0))
        self.drawer_lbl_mods.setStyleSheet("font-size: 11px; color: #94a3b8;")
        ed_layout.addWidget(self.drawer_lbl_mods)

        self.drawer_lbl_last_sync = QLabel(tr("drawer.last_scan", time=tr("common.pending")))
        self.drawer_lbl_last_sync.setStyleSheet("font-size: 10px; color: #64748b;")
        ed_layout.addWidget(self.drawer_lbl_last_sync)

        # Subcategories
        self.lbl_subcats = QLabel(tr("drawer.subcats_title"))
        self.lbl_subcats.setStyleSheet("font-size: 11px; font-weight: 700; color: #60a5fa; margin-top: 4px;")
        ed_layout.addWidget(self.lbl_subcats)

        subcats_scroll = QScrollArea()
        subcats_scroll.setFixedHeight(180)
        subcats_scroll.setWidgetResizable(True)
        subcats_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #0a0d1c;
                border: 1px solid #1a223e;
                border-radius: 6px;
            }
        """)
        self.subcats_container = QWidget()
        self.subcats_layout = QVBoxLayout(self.subcats_container)
        self.subcats_layout.setContentsMargins(6, 6, 6, 6)
        self.subcats_layout.setSpacing(4)
        subcats_scroll.setWidget(self.subcats_container)
        ed_layout.addWidget(subcats_scroll)

        self._init_subcategory_rows()

        # Scraping Action Controls
        ctrl_layout = QVBoxLayout()
        ctrl_layout.setSpacing(6)

        self.btn_resync = QPushButton(tr("drawer.btn_resync"))
        self.btn_resync.setFixedHeight(32)
        self.btn_resync.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_resync_button()
        self.btn_resync.clicked.connect(lambda: self.start_requested.emit("loverslab"))
        ctrl_layout.addWidget(self.btn_resync)

        btn_sub_row = QHBoxLayout()
        btn_sub_row.setSpacing(6)

        self.btn_pause_resume = QPushButton(tr("drawer.btn_pause"))
        self.btn_pause_resume.setFixedHeight(30)
        self.btn_pause_resume.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_pause_button(is_paused=False)
        self.btn_pause_resume.setEnabled(False)
        self.btn_pause_resume.clicked.connect(self._on_pause_resume_clicked)
        btn_sub_row.addWidget(self.btn_pause_resume, stretch=1)

        self.btn_stop = QPushButton(tr("drawer.btn_stop"))
        self.btn_stop.setFixedHeight(30)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_stop_button()
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(lambda: self.stop_requested.emit("loverslab"))
        btn_sub_row.addWidget(self.btn_stop, stretch=1)

        ctrl_layout.addLayout(btn_sub_row)
        ed_layout.addLayout(ctrl_layout)

        ll_layout.addWidget(self.ll_expanded_details)
        providers_layout.addWidget(ll_card)

        # --- Extensible: Patreon Card ---
        patreon_card = QFrame()
        patreon_card.setStyleSheet("""
            QFrame {
                background-color: #13172e;
                border: 1px solid #222d52;
                border-radius: 8px;
                padding: 6px;
            }
        """)
        p_card_layout = QVBoxLayout(patreon_card)
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
        providers_layout.addWidget(patreon_card)

        providers_layout.addStretch()
        drawer_scroll.setWidget(providers_container)
        d_layout.addWidget(drawer_scroll)

        main_layout.addWidget(self.drawer_panel)

    def _init_subcategory_rows(self):
        """Initializes the subcategory rows in the progress area using SubcategoryRowWidget."""
        subcategories_meta = [
            ("174", "WickedWhims", "🔞"),
            ("201", "Animations : WickedWhims", "💃"),
            ("215", "Translations : WickedWhims", "🌐"),
            ("202", "Animations : Other", "🎬"),
            ("200", "Extensions", "🧩"),
            ("203", "Clothing", "👗"),
            ("204", "Accessories & Makeup", "💄"),
            ("205", "Body Parts", "✨"),
            ("206", "Objects", "🛋️"),
            ("404", "Paintings & Posters", "🖼️"),
            ("207", "Lots", "🏡"),
            ("209", "Translations", "🌐"),
            ("210", "Other", "📦"),
            ("216", "Uncategorized", "📁"),
        ]

        for cid, cname, cicon in subcategories_meta:
            row_widget = SubcategoryRowWidget(cid, cname, cicon, parent=self.subcats_container)
            self.subcats_layout.addWidget(row_widget)
            self.subcat_widgets[cid] = row_widget
            self.subcat_rows[cid] = row_widget.labels_tuple

    def toggle_drawer(self):
        """Toggles visibility of the drawer panel."""
        new_vis = not self.drawer_panel.isVisible()
        self.drawer_panel.setVisible(new_vis)
        arrow = "▶" if new_vis else "◀"
        cur_t = self.btn_toggle_drawer.text()
        parts = cur_t.rsplit(" ", 1)
        base = parts[0] if len(parts) > 1 else cur_t
        self.btn_toggle_drawer.setText(f"{base} {arrow}")

    def _toggle_loverslab_section(self):
        self._ll_is_expanded = not self._ll_is_expanded
        self.ll_expanded_details.setVisible(self._ll_is_expanded)
        self.ll_collapsed_summary.setVisible(not self._ll_is_expanded)
        self.btn_collapse_ll.setText("▼" if self._ll_is_expanded else "▲")

    def _on_pause_resume_clicked(self):
        is_paused = getattr(self, "_current_is_paused", False)
        if is_paused:
            self.resume_requested.emit("loverslab")
        else:
            self.pause_requested.emit("loverslab")

    def update_sync_status(self, status: Dict[str, Any]):
        """Updates drawer status, progress bar, action buttons, and persistent tab."""
        self._last_status = status
        is_running = status.get("is_running", False)
        is_paused = status.get("is_paused", False)
        is_stopped = status.get("is_stopped", False)
        pct = status.get("progress_percent", 0)
        pages_done = status.get("pages_completed", 0)
        total_pages = status.get("total_pages", 0)
        cur_cat = status.get("current_category") or tr("common.ready")
        has_error = status.get("has_error", False)
        total_scraped = status.get("total_scraped", 0)
        last_completed = status.get("last_completed_at") or ""
        categories_progress = status.get("categories_progress", [])

        self._current_is_paused = is_paused
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

        # 2. Update Header Status Pill
        if has_error:
            self._style_status_pill("ERROR", tr("drawer.status_error"))
        elif is_paused:
            self._style_status_pill("PAUSED", f"{tr('drawer.status_paused')} ({pct}%)")
        elif is_running:
            self._style_status_pill("RUNNING", f"{tr('drawer.status_running')} ({pct}%)")
        elif is_stopped:
            self._style_status_pill("STOPPED", tr("drawer.status_stopped"))
        else:
            self._style_status_pill("OK", tr("drawer.status_ready"))

        # 3. Update Progress Bar and textual details
        self.drawer_progress_bar.setValue(pct)
        self.drawer_lbl_progress.setText(tr("drawer.progress", done=pages_done, total=total_pages, pct=pct))
        self.drawer_lbl_category.setText(tr("drawer.category_current", cat=cur_cat))
        self.drawer_lbl_mods.setText(tr("drawer.mods_count", count=total_scraped))
        if last_completed:
            self.drawer_lbl_last_sync.setText(tr("drawer.last_scan", time=last_completed))

        # Collapsed Summary Text
        self.ll_collapsed_summary_lbl.setText(
            f"{cur_cat} • {pct}% ({total_scraped} mods)" if is_running or is_paused else tr("drawer.summary", count=total_scraped)
        )

        # 4. Action Buttons State
        if is_running:
            self.btn_resync.setText(tr("drawer.btn_in_progress"))
            self.btn_resync.setEnabled(False)
            self._style_resync_button(loading=True)

            self.btn_pause_resume.setText(tr("drawer.btn_pause"))
            self.btn_pause_resume.setEnabled(True)
            self._style_pause_button(is_paused=False)

            self.btn_stop.setEnabled(True)
            self._style_stop_button(disabled=False)
        elif is_paused:
            self.btn_resync.setText(tr("drawer.btn_in_progress"))
            self.btn_resync.setEnabled(False)
            self._style_resync_button(is_paused=True)

            self.btn_pause_resume.setText(tr("drawer.btn_resume"))
            self.btn_pause_resume.setEnabled(True)
            self._style_pause_button(is_paused=True)

            self.btn_stop.setEnabled(True)
            self._style_stop_button(disabled=False)
        else:
            self.btn_resync.setText(tr("drawer.btn_resync"))
            self.btn_resync.setEnabled(True)
            self._style_resync_button(loading=False)

            self.btn_pause_resume.setText(tr("drawer.btn_pause"))
            self.btn_pause_resume.setEnabled(False)
            self._style_pause_button(disabled=True)

            self.btn_stop.setEnabled(False)
            self._style_stop_button(disabled=True)

        # 5. Update Subcategory Progress Rows
        for cat_info in categories_progress:
            cid = str(cat_info.get("id") or getattr(cat_info, "id", ""))
            row_widget = self.subcat_widgets.get(cid)
            if not row_widget:
                continue

            status_val = cat_info.get("status") if isinstance(cat_info, dict) else getattr(cat_info, "status", "PENDING")
            p_done = cat_info.get("pages_completed", 0) if isinstance(cat_info, dict) else getattr(cat_info, "pages_completed", 0)
            p_total = cat_info.get("total_pages", 0) if isinstance(cat_info, dict) else getattr(cat_info, "total_pages", 0)
            m_cnt = cat_info.get("mods_count", 0) if isinstance(cat_info, dict) else getattr(cat_info, "mods_count", 0)

            if status_val == "COMPLETED":
                row_widget.set_status(f"Terminé ({m_cnt} mods)", "#34d399")
            elif status_val == "IN_PROGRESS":
                row_widget.set_status(f"p.{p_done}/{p_total} ({m_cnt})", "#60a5fa")
            elif status_val == "STOPPED":
                row_widget.set_status(f"Arrêté ({p_done}/{p_total})", "#f59e0b")
            elif status_val == "ERROR":
                row_widget.set_status("Erreur", "#f87171")
            else:
                row_widget.set_status("Attente", "#64748b")

    def retranslate_ui(self):
        """Retranslates all static and dynamic UI texts according to current language."""
        self.d_title.setText(tr("drawer.title"))
        self.lbl_subcats.setText(tr("drawer.subcats_title"))
        self.p_desc.setText(tr("drawer.patreon_desc"))
        self.btn_toggle_drawer.setToolTip(tr("drawer.btn_toggle_tip"))
        self.tab_loverslab_pill.setToolTip(tr("drawer.pill_tip_ll"))
        self.tab_patreon_pill.setToolTip(tr("drawer.pill_tip_patreon"))
        self.patreon_status_pill.setText(tr("drawer.status_ready"))

        if self._last_status:
            self.update_sync_status(self._last_status)
        else:
            arrow = "▶" if self.drawer_panel.isVisible() else "◀"
            self.btn_toggle_drawer.setText(f"🛰️ Sites {arrow}")
            self._style_status_pill("OK", tr("drawer.status_ready"))
            self.ll_collapsed_summary_lbl.setText(tr("drawer.summary", count=0))
            self.drawer_lbl_progress.setText(tr("drawer.progress", done=0, total=0, pct=0))
            self.drawer_lbl_category.setText(tr("drawer.category_current", cat=tr("common.ready")))
            self.drawer_lbl_mods.setText(tr("drawer.mods_count", count=0))
            self.drawer_lbl_last_sync.setText(tr("drawer.last_scan", time=tr("common.pending")))
            self.btn_resync.setText(tr("drawer.btn_resync"))
            self.btn_pause_resume.setText(tr("drawer.btn_pause"))
            self.btn_stop.setText(tr("drawer.btn_stop"))

    # --- Delegated Styling Helpers with Dirty Checking ---
    def _style_status_pill(self, state: str, text: Optional[str] = None):
        if text:
            self.drawer_status_pill.setText(text)
        if getattr(self, "_last_status_pill_state", None) == state:
            return
        self._last_status_pill_state = state
        self.drawer_status_pill.setStyleSheet(DrawerStyles.status_pill(state))

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

    def _style_resync_button(self, loading: bool = False, is_paused: bool = False):
        self.btn_resync.setStyleSheet(DrawerStyles.resync_button(loading, is_paused))

    def _style_pause_button(self, is_paused: bool = False, disabled: bool = False):
        self.btn_pause_resume.setStyleSheet(DrawerStyles.pause_button(is_paused, disabled))

    def _style_stop_button(self, disabled: bool = False):
        self.btn_stop.setStyleSheet(DrawerStyles.stop_button(disabled))
