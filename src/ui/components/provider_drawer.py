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

        # Scraping Action Controls: [Relancer / Démarrer], [Pause / Reprendre], [Arrêter]
        ctrl_layout = QVBoxLayout()
        ctrl_layout.setSpacing(6)

        # Primary start / resync button
        self.btn_resync = QPushButton(tr("drawer.btn_resync"))
        self.btn_resync.setFixedHeight(32)
        self.btn_resync.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_resync_button()
        self.btn_resync.clicked.connect(lambda: self.start_requested.emit("loverslab"))
        ctrl_layout.addWidget(self.btn_resync)

        # Secondary action row: [Pause / Reprendre] and [Arrêter]
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
        """Initializes the 14 subcategory rows in the progress area."""
        subcategories_meta = [
            ("330", "Modding : Base Mods", "⚙️"),
            ("331", "Animations : WickedWhims", "💃"),
            ("332", "Animations : General", "🎬"),
            ("333", "Poses & Scénarios", "📸"),
            ("334", "Vêtements : Féminin", "👗"),
            ("335", "Vêtements : Masculin", "👔"),
            ("336", "Coiffures & Beauté", "💇"),
            ("337", "Objets & Décorations", "🛋️"),
            ("338", "Skins & Peaux", "✨"),
            ("339", "Accessoires & Bijoux", "💍"),
            ("340", "Tatouages & Détails", "🎨"),
            ("341", "Maisons & Terrains", "🏡"),
            ("342", "Traits & Aspirations", "🧠"),
            ("343", "Traductions & Autres", "🌐"),
        ]

        for cid, cname, cicon in subcategories_meta:
            row_frame = QFrame()
            row_frame.setStyleSheet("""
                QFrame {
                    background-color: #0e1224;
                    border: 1px solid #161e38;
                    border-radius: 4px;
                    padding: 2px 4px;
                }
            """)
            r_layout = QHBoxLayout(row_frame)
            r_layout.setContentsMargins(4, 2, 4, 2)
            r_layout.setSpacing(6)

            lbl_icon = QLabel(cicon)
            lbl_icon.setFixedWidth(16)
            r_layout.addWidget(lbl_icon)

            lbl_name = QLabel(cname)
            lbl_name.setStyleSheet("font-size: 10px; color: #cbd5e1; font-weight: 500;")
            r_layout.addWidget(lbl_name, stretch=1)

            lbl_detail = QLabel("Attente")
            lbl_detail.setStyleSheet("font-size: 9px; color: #64748b;")
            lbl_detail.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            r_layout.addWidget(lbl_detail)

            self.subcats_layout.addWidget(row_frame)
            self.subcat_rows[cid] = (lbl_icon, lbl_name, lbl_detail)

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

        # 3. Update Progress and Category Stats
        self.ll_collapsed_summary_lbl.setText(
            f"{tr('drawer.summary', count=total_scraped)} • p.{pages_done}/{total_pages}"
        )
        self.drawer_progress_bar.setValue(pct)
        if total_pages > 0:
            self.drawer_lbl_progress.setText(tr("drawer.progress", done=pages_done, total=total_pages, pct=pct))
        else:
            self.drawer_lbl_progress.setText(f"📄 Page {pages_done}")
        if not is_running and not is_paused:
            self.drawer_lbl_category.setText(f"📂 {tr('common.status')} : {tr('common.completed')}")
        elif is_paused:
            self.drawer_lbl_category.setText(f"📂 {tr('drawer.status_paused')} : {cur_cat}")
        else:
            self.drawer_lbl_category.setText(tr("drawer.category_current", cat=cur_cat))
        self.drawer_lbl_mods.setText(tr("drawer.mods_count", count=total_scraped))
        if last_completed:
            date_part = last_completed.replace("T", " ")[:19]
            self.drawer_lbl_last_sync.setText(tr("drawer.last_scan", time=date_part))

        # 4. Update Subcategory Rows
        for cat_item in categories_progress:
            cid = str(cat_item.get("id"))
            if cid in self.subcat_rows:
                lbl_icon, lbl_name, lbl_detail = self.subcat_rows[cid]
                c_stat = cat_item.get("status", "PENDING")
                c_done = cat_item.get("pages_completed", 0)
                c_total = cat_item.get("total_pages", 0)
                c_mods = cat_item.get("mods_count", 0)

                completed_text = tr("common.completed")
                if not is_running and not is_paused and not is_stopped:
                    lbl_icon.setText("🟢")
                    if c_done > 0:
                        lbl_detail.setText(f"{c_done}/{c_total} p. ({c_mods} mods)")
                    elif c_mods > 0:
                        lbl_detail.setText(f"{completed_text} ({c_mods} mods)")
                    else:
                        lbl_detail.setText(f"{completed_text} ({c_total} p.)")
                    lbl_detail.setStyleSheet("font-size: 9px; color: #a7f3d0; font-weight: 600;")
                elif is_paused and c_stat == "IN_PROGRESS":
                    lbl_icon.setText("⏸️")
                    lbl_detail.setText(f"{tr('drawer.status_paused')} (p. {c_done}/{c_total})")
                    lbl_detail.setStyleSheet("font-size: 9px; color: #fbbf24; font-weight: 600;")
                elif c_stat == "COMPLETED":
                    lbl_icon.setText("🟢")
                    lbl_detail.setText(f"{c_done}/{c_total} p. ({c_mods} mods)")
                    lbl_detail.setStyleSheet("font-size: 9px; color: #a7f3d0; font-weight: 600;")
                elif c_stat == "IN_PROGRESS":
                    lbl_icon.setText("🔵")
                    lbl_detail.setText(f"p. {c_done}/{c_total} ({c_mods} mods)")
                    lbl_detail.setStyleSheet("font-size: 9px; color: #93c5fd; font-weight: 600;")
                elif c_stat == "STOPPED":
                    lbl_icon.setText("⏹️")
                    lbl_detail.setText(f"{tr('drawer.status_stopped')} ({c_done} p.)")
                    lbl_detail.setStyleSheet("font-size: 9px; color: #fbbf24;")
                elif c_stat == "ERROR":
                    lbl_icon.setText("🔴")
                    lbl_detail.setText(tr("common.error"))
                    lbl_detail.setStyleSheet("font-size: 9px; color: #fca5a5;")
                else:
                    lbl_icon.setText("⏳")
                    lbl_detail.setText(f"{tr('common.pending')} ({c_total} p.)")
                    lbl_detail.setStyleSheet("font-size: 9px; color: #64748b;")

        # 5. Update Control Buttons States
        if is_running:
            self.btn_pause_resume.setEnabled(True)
            self.btn_stop.setEnabled(True)

            if is_paused:
                self.btn_resync.setEnabled(False)
                self.btn_resync.setText(tr("drawer.scraping_paused"))
                self._style_resync_button(loading=True, is_paused=True)

                self.btn_pause_resume.setText(tr("drawer.btn_resume"))
                self._style_pause_button(is_paused=True)
            else:
                self.btn_resync.setEnabled(False)
                self.btn_resync.setText(tr("drawer.scraping_running"))
                self._style_resync_button(loading=True, is_paused=False)

                self.btn_pause_resume.setText(tr("drawer.btn_pause"))
                self._style_pause_button(is_paused=False)
        else:
            self.btn_resync.setEnabled(True)
            self.btn_resync.setText(tr("drawer.btn_resync"))
            self._style_resync_button(loading=False, is_paused=False)

            self.btn_pause_resume.setEnabled(False)
            self.btn_pause_resume.setText(tr("drawer.btn_pause"))
            self._style_pause_button(is_paused=False, disabled=True)

            self.btn_stop.setEnabled(False)
            self.btn_stop.setText(tr("drawer.btn_stop"))
            self._style_stop_button(disabled=True)

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

    # --- Styling Helpers ---
    def _style_status_pill(self, state: str, text: Optional[str] = None):
        if state == "ERROR":
            self.drawer_status_pill.setText(text or tr("drawer.status_error"))
            self.drawer_status_pill.setStyleSheet("""
                background-color: #450a0a; color: #fca5a5;
                border: 1px solid #dc2626; border-radius: 4px;
                padding: 2px 6px; font-size: 10px; font-weight: 700;
            """)
        elif state == "PAUSED":
            self.drawer_status_pill.setText(text or "⏸️ En pause")
            self.drawer_status_pill.setStyleSheet("""
                background-color: #451a03; color: #fde68a;
                border: 1px solid #d97706; border-radius: 4px;
                padding: 2px 6px; font-size: 10px; font-weight: 700;
            """)
        elif state == "RUNNING":
            self.drawer_status_pill.setText(text or "🔵 En cours")
            self.drawer_status_pill.setStyleSheet("""
                background-color: #1e1b4b; color: #93c5fd;
                border: 1px solid #3b82f6; border-radius: 4px;
                padding: 2px 6px; font-size: 10px; font-weight: 700;
            """)
        elif state == "STOPPED":
            self.drawer_status_pill.setText(text or "⏹️ Arrêté")
            self.drawer_status_pill.setStyleSheet("""
                background-color: #262626; color: #d4d4d8;
                border: 1px solid #52525b; border-radius: 4px;
                padding: 2px 6px; font-size: 10px; font-weight: 700;
            """)
        else:
            self.drawer_status_pill.setText(text or "🟢 Prêt / Terminé")
            self.drawer_status_pill.setStyleSheet("""
                background-color: #064e3b; color: #a7f3d0;
                border: 1px solid #059669; border-radius: 4px;
                padding: 2px 6px; font-size: 10px; font-weight: 700;
            """)

    def _style_toggle_button(self, state: str):
        if state == "ERROR":
            bg, border = "#450a0a", "#dc2626"
        elif state == "PAUSED":
            bg, border = "#451a03", "#d97706"
        elif state == "RUNNING":
            bg, border = "#1e1b4b", "#3b82f6"
        else:
            bg, border = "#111827", "#1f2937"

        self.btn_toggle_drawer.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: #f8fafc;
                border: 1px solid {border};
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: #1f293d; }}
        """)

    def _style_site_tab_pill(self, label: QLabel, state: str, text: str):
        label.setText(text)
        if state == "ERROR":
            label.setStyleSheet("""
                background-color: #450a0a; color: #fca5a5;
                border: 1px solid #dc2626; border-radius: 6px;
                padding: 4px 6px; font-size: 11px; font-weight: 700;
            """)
        elif state == "PAUSED":
            label.setStyleSheet("""
                background-color: #451a03; color: #fde68a;
                border: 1px solid #d97706; border-radius: 6px;
                padding: 4px 6px; font-size: 11px; font-weight: 700;
            """)
        elif state == "RUNNING":
            label.setStyleSheet("""
                background-color: #1e1b4b; color: #93c5fd;
                border: 1px solid #3b82f6; border-radius: 6px;
                padding: 4px 6px; font-size: 11px; font-weight: 700;
            """)
        else:
            label.setStyleSheet("""
                background-color: #064e3b; color: #a7f3d0;
                border: 1px solid #059669; border-radius: 6px;
                padding: 4px 6px; font-size: 11px; font-weight: 700;
            """)

    def _style_resync_button(self, loading: bool = False, is_paused: bool = False):
        if is_paused:
            self.btn_resync.setStyleSheet("""
                QPushButton {
                    background-color: #451a03;
                    color: #fde68a;
                    border: 1px solid #d97706;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 700;
                }
            """)
        elif loading:
            self.btn_resync.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #64748b;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 700;
                }
            """)
        else:
            self.btn_resync.setStyleSheet("""
                QPushButton {
                    background-color: #1d4ed8;
                    color: #ffffff;
                    border: 1px solid #3b82f6;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 700;
                }
                QPushButton:hover { background-color: #2563eb; }
            """)

    def _style_pause_button(self, is_paused: bool = False, disabled: bool = False):
        if disabled:
            self.btn_pause_resume.setStyleSheet("""
                QPushButton {
                    background-color: #1e2538;
                    color: #475569;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 600;
                }
            """)
        elif is_paused:
            self.btn_pause_resume.setStyleSheet("""
                QPushButton {
                    background-color: #1e3a8a;
                    color: #93c5fd;
                    border: 1px solid #3b82f6;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover { background-color: #2563eb; color: #ffffff; }
            """)
        else:
            self.btn_pause_resume.setStyleSheet("""
                QPushButton {
                    background-color: #78350f;
                    color: #fde68a;
                    border: 1px solid #d97706;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover { background-color: #92400e; color: #ffffff; }
            """)

    def _style_stop_button(self, disabled: bool = False):
        if disabled:
            self.btn_stop.setStyleSheet("""
                QPushButton {
                    background-color: #1e2538;
                    color: #475569;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 600;
                }
            """)
        else:
            self.btn_stop.setStyleSheet("""
                QPushButton {
                    background-color: #7f1d1d;
                    color: #fecaca;
                    border: 1px solid #dc2626;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover { background-color: #991b1b; color: #ffffff; }
            """)
