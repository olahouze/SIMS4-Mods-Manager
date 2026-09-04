import math
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QProgressBar,
    QMessageBox,
    QDialog,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer

from src.api.client import get_api_client
from src.ui.components.filter_bar import FilterBar
from src.ui.components.mod_card import ModCard
from src.ui.components.dependencies_dialog import DependenciesDialog
from src.ui.components.progress_dialog import ProgressDialog
from src.utils.logger import logger


class SyncTriggerWorker(QThread):
    finished_signal = Signal(bool, str)

    def __init__(self, api_client, max_pages: int = 0):
        super().__init__()
        self.api_client = api_client
        self.max_pages = max_pages

    def run(self):
        try:
            self.api_client.start_catalog_sync(max_pages=self.max_pages)
            self.finished_signal.emit(True, "OK")
        except Exception as e:
            self.finished_signal.emit(False, str(e))


class InstallWorker(QThread):
    progress = Signal(int, str, str)  # percent, status, details
    finished = Signal(bool, str)

    def __init__(self, mod_data: dict):
        super().__init__()
        self.mod_data = mod_data

    def run(self):
        client = get_api_client()
        try:
            self.progress.emit(2, "Initialisation de l'installation...", "Préparation de la requête...")
            u_date = self.mod_data.get("updated_date")
            u_date_str = u_date.isoformat() if hasattr(u_date, "isoformat") else (str(u_date) if u_date else None)

            payload = {
                "catalog_mod_id": self.mod_data.get("id"),
                "source": self.mod_data.get("source"),
                "remote_id": self.mod_data.get("remote_id"),
                "page_url": self.mod_data.get("page_url"),
                "title": self.mod_data.get("title"),
                "updated_date": u_date_str,
                "install_dependencies": True,
            }

            for event in client.install_mod_stream(payload):
                evt_type = event.get("type")
                if evt_type == "progress":
                    pct = event.get("percent", 0)
                    st = event.get("status", "Installation...")
                    det = event.get("details", "")
                    logger.info(f"[INSTALL-PROGRESS] [{pct}%] {st} {f'({det})' if det else ''}")
                    self.progress.emit(pct, st, det)
                elif evt_type == "finished":
                    success = event.get("success", False)
                    msg = event.get("message", "")
                    if not success:
                        logger.error(f"Échec de l'installation du mod '{self.mod_data.get('title')}': {msg}")
                    else:
                        logger.info(f"Mod '{self.mod_data.get('title')}' installé avec succès: {msg}")
                    self.finished.emit(success, msg)
                    return

            self.finished.emit(True, "Installation terminée.")
        except Exception as e:
            logger.error(f"Erreur API lors de l'installation du mod '{self.mod_data.get('title')}': {e}", exc_info=True)
            self.finished.emit(False, f"Erreur API lors de l'installation: {e}")


class CatalogView(QWidget):
    """
    Unified multi-source mod catalog view with grid layout, search/filter bar,
    progressive page-1 immediate rendering, background sync monitoring, and pagination.
    """

    details_requested = Signal(dict)
    install_finished = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.current_page = 1
        self.page_size = 24
        self.total_items = 0
        self.total_pages = 1

        self._page1_displayed = False
        self._last_pages_completed = 0

        # Background sync monitoring timer (runs continuously to keep status icon accurate)
        self.monitor_timer = QTimer(self)
        self.monitor_timer.setInterval(1200)
        self.monitor_timer.timeout.connect(self._check_sync_status)
        self.monitor_timer.start()

        self.init_ui()

    def init_ui(self):
        main_h_layout = QHBoxLayout(self)
        main_h_layout.setContentsMargins(18, 18, 18, 18)
        main_h_layout.setSpacing(12)

        # Left Column: Unified Catalog
        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Header Title
        title = QLabel("Catalogue Unifié des Mods")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title)

        # Non-blocking Sync Progress Banner
        self.sync_banner = QFrame()
        self.sync_banner.setObjectName("SyncBanner")
        self.sync_banner.setVisible(False)
        self.sync_banner.setStyleSheet("""
            QFrame#SyncBanner {
                background-color: #1a1d30;
                border: 1px solid #4f46e5;
                border-radius: 8px;
                padding: 10px 14px;
            }
        """)
        b_layout = QHBoxLayout(self.sync_banner)
        b_layout.setContentsMargins(0, 0, 0, 0)
        b_layout.setSpacing(12)

        self.sync_banner_lbl = QLabel("🔄 Synchronisation en arrière-plan...")
        self.sync_banner_lbl.setStyleSheet("font-size: 12px; color: #cbd5e1; font-weight: 600;")
        b_layout.addWidget(self.sync_banner_lbl, stretch=2)

        self.sync_bar = QProgressBar()
        self.sync_bar.setFixedHeight(12)
        self.sync_bar.setRange(0, 100)
        self.sync_bar.setValue(0)
        self.sync_bar.setTextVisible(False)
        self.sync_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0f172a;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background-color: #6366f1;
                border-radius: 6px;
            }
        """)
        b_layout.addWidget(self.sync_bar, stretch=1)

        layout.addWidget(self.sync_banner)

        # Filter Bar
        self.filter_bar = FilterBar()
        self.filter_bar.filters_changed.connect(self._on_filters_changed)
        layout.addWidget(self.filter_bar)

        # Scroll Area with Card Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll, stretch=1)

        # Pagination Bar
        self.pagination_bar = QFrame()
        self.pagination_bar.setStyleSheet("""
            QFrame {
                background-color: #121422;
                border: 1px solid #1e2438;
                border-radius: 8px;
                padding: 6px 12px;
            }
        """)
        p_layout = QHBoxLayout(self.pagination_bar)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(12)

        self.btn_prev = QPushButton("◀ Précédent")
        self.btn_prev.setFixedHeight(30)
        self.btn_prev.setStyleSheet("""
            QPushButton {
                background-color: #1e2438;
                color: #cbd5e1;
                border: 1px solid #2d3748;
                border-radius: 6px;
                padding: 4px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2b3552; color: #ffffff; }
            QPushButton:disabled { background-color: #121520; color: #475569; border-color: #1e2438; }
        """)
        self.btn_prev.clicked.connect(self._on_prev_page)
        p_layout.addWidget(self.btn_prev)

        self.lbl_page_info = QLabel("Page 1 sur 1 (0 mods)")
        self.lbl_page_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_page_info.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 600;")
        p_layout.addWidget(self.lbl_page_info, stretch=1)

        self.btn_next = QPushButton("Suivant ▶")
        self.btn_next.setFixedHeight(30)
        self.btn_next.setStyleSheet("""
            QPushButton {
                background-color: #1e2438;
                color: #cbd5e1;
                border: 1px solid #2d3748;
                border-radius: 6px;
                padding: 4px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2b3552; color: #ffffff; }
            QPushButton:disabled { background-color: #121520; color: #475569; border-color: #1e2438; }
        """)
        self.btn_next.clicked.connect(self._on_next_page)
        p_layout.addWidget(self.btn_next)

        layout.addWidget(self.pagination_bar)
        main_h_layout.addWidget(left_widget, stretch=1)

        # Right Column: Persistent Status Tab + Retractable Drawer
        right_container = QWidget()
        right_h_layout = QHBoxLayout(right_container)
        right_h_layout.setContentsMargins(0, 0, 0, 0)
        right_h_layout.setSpacing(6)

        # Persistent Toggle Tab (Always visible on edge for individual site statuses)
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

        self.btn_toggle_drawer = QPushButton("🛰️ Sites ◀")
        self.btn_toggle_drawer.setFixedHeight(32)
        self.btn_toggle_drawer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_drawer.setToolTip("Cliquer pour ouvrir / fermer le tiroir de statut des scrapers")
        self.btn_toggle_drawer.clicked.connect(self._toggle_drawer)
        self._style_toggle_button("OK")
        tab_layout.addWidget(self.btn_toggle_drawer)

        # Site status badge for LoversLab (always visible on collapsed edge)
        self.tab_loverslab_pill = QLabel("LoversLab 🟢")
        self.tab_loverslab_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tab_loverslab_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_loverslab_pill.setToolTip("Statut LoversLab - Cliquer pour ouvrir les détails")
        self.tab_loverslab_pill.mousePressEvent = lambda e: self._toggle_drawer()
        self._style_site_tab_pill(self.tab_loverslab_pill, "OK", "LoversLab 🟢")
        tab_layout.addWidget(self.tab_loverslab_pill)

        # Extensible: future site status badge for Patreon
        self.tab_patreon_pill = QLabel("Patreon 🟢")
        self.tab_patreon_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tab_patreon_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_patreon_pill.setToolTip("Statut Patreon - Prêt")
        self.tab_patreon_pill.mousePressEvent = lambda e: self._toggle_drawer()
        self._style_site_tab_pill(self.tab_patreon_pill, "OK", "Patreon 🟢")
        tab_layout.addWidget(self.tab_patreon_pill)

        tab_layout.addStretch()
        right_h_layout.addWidget(self.tab_widget)

        # Retractable Drawer Panel
        self.drawer_panel = QFrame()
        self.drawer_panel.setObjectName("DrawerPanel")
        self.drawer_panel.setFixedWidth(340)
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
        d_title = QLabel("🛰️ Fournisseurs de Mods")
        d_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #f8fafc;")
        d_header.addWidget(d_title)
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
        btn_close.clicked.connect(self._toggle_drawer)
        d_header.addWidget(btn_close)
        d_layout.addLayout(d_header)

        # Scrollable area containing provider sections (extensible for future sites)
        drawer_scroll = QScrollArea()
        drawer_scroll.setWidgetResizable(True)
        drawer_scroll.setStyleSheet("background-color: transparent; border: none;")

        providers_container = QWidget()
        providers_layout = QVBoxLayout(providers_container)
        providers_layout.setContentsMargins(0, 0, 0, 0)
        providers_layout.setSpacing(10)

        # --- LoversLab Provider Accordion Card ---
        self._ll_is_expanded = True
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

        # LoversLab Header
        ll_header = QHBoxLayout()
        ll_name = QLabel("LoversLab")
        ll_name.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        ll_header.addWidget(ll_name)
        ll_header.addStretch()

        self.drawer_status_pill = QLabel("🟢 Prêt")
        self.drawer_status_pill.setStyleSheet("""
            background-color: #064e3b;
            color: #a7f3d0;
            border: 1px solid #059669;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 700;
        """)
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

        # Collapsed Summary (visible ONLY when collapsed)
        self.ll_collapsed_summary = QWidget()
        cs_layout = QVBoxLayout(self.ll_collapsed_summary)
        cs_layout.setContentsMargins(0, 2, 0, 2)
        cs_layout.setSpacing(4)
        self.ll_collapsed_summary_lbl = QLabel("14 sous-catégories • 0 mods")
        self.ll_collapsed_summary_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        cs_layout.addWidget(self.ll_collapsed_summary_lbl)
        self.ll_collapsed_summary.setVisible(False)
        ll_layout.addWidget(self.ll_collapsed_summary)

        # Expanded Details Widget (visible when expanded)
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

        self.drawer_lbl_progress = QLabel("📄 Progression : 0 / 0 pages (0%)")
        self.drawer_lbl_progress.setStyleSheet("font-size: 11px; color: #cbd5e1; font-weight: 600;")
        ed_layout.addWidget(self.drawer_lbl_progress)

        self.drawer_lbl_category = QLabel("📂 En cours : Prêt")
        self.drawer_lbl_category.setStyleSheet("font-size: 11px; color: #94a3b8;")
        ed_layout.addWidget(self.drawer_lbl_category)

        self.drawer_lbl_mods = QLabel("📦 Mods indexés : 0")
        self.drawer_lbl_mods.setStyleSheet("font-size: 11px; color: #94a3b8;")
        ed_layout.addWidget(self.drawer_lbl_mods)

        self.drawer_lbl_last_sync = QLabel("🕒 Dernier scan : En attente")
        self.drawer_lbl_last_sync.setStyleSheet("font-size: 10px; color: #64748b;")
        ed_layout.addWidget(self.drawer_lbl_last_sync)

        # Subcategories Title
        lbl_subcats = QLabel("Progression par sous-catégorie (14) :")
        lbl_subcats.setStyleSheet("font-size: 11px; font-weight: 700; color: #60a5fa; margin-top: 4px;")
        ed_layout.addWidget(lbl_subcats)

        # Subcategories scroll area
        subcats_scroll = QScrollArea()
        subcats_scroll.setFixedHeight(200)
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

        # Initialize subcategory row widgets dictionary
        self.subcat_rows = {}
        self._init_subcategory_rows()

        # Resync button
        self.btn_resync = QPushButton("🔄 Relancer LoversLab")
        self.btn_resync.setFixedHeight(34)
        self.btn_resync.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_resync_button()
        self.btn_resync.clicked.connect(lambda: self.start_sync(max_pages=0))
        ed_layout.addWidget(self.btn_resync)

        ll_layout.addWidget(self.ll_expanded_details)
        providers_layout.addWidget(ll_card)

        # --- Extensible: Patreon Card (Future provider demo) ---
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
        p_status = QLabel("🟢 Prêt")
        p_status.setStyleSheet("""
            background-color: #064e3b;
            color: #a7f3d0;
            border: 1px solid #059669;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 700;
        """)
        p_header.addWidget(p_status)
        p_card_layout.addLayout(p_header)
        p_desc = QLabel("Vérification des accès abonnés et liens de téléchargement.")
        p_desc.setStyleSheet("font-size: 10px; color: #64748b;")
        p_card_layout.addWidget(p_desc)
        providers_layout.addWidget(patreon_card)

        providers_layout.addStretch()
        drawer_scroll.setWidget(providers_container)
        d_layout.addWidget(drawer_scroll)

        right_h_layout.addWidget(self.drawer_panel)
        main_h_layout.addWidget(right_container)

        # Initial data load
        self.refresh_catalog()

        # Check sync status immediately on startup
        self._check_sync_status()

    def _on_filters_changed(self):
        """Reset to page 1 when user changes search query or filters."""
        self.current_page = 1
        self.refresh_catalog()

    def _on_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_catalog()

    def _on_next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.refresh_catalog()

    def refresh_catalog(self):
        """Clears and re-populates the catalog grid with filtered and paginated items from API."""
        filter_state = self.filter_bar.get_filter_state()

        source_param = None
        if filter_state["source"] == "LoversLab":
            source_param = "loverslab"
        elif filter_state["source"] == "Patreon":
            source_param = "patreon"

        access_param = None
        acc_text = filter_state["access"]
        if "Directement" in acc_text:
            access_param = "direct"
        elif "connexion" in acc_text.lower():
            access_param = "needs_account"
        elif "abonnement" in acc_text.lower() and "débloqué" not in acc_text.lower():
            access_param = "needs_sub"
        elif "Débloqué" in acc_text:
            access_param = "unlocked"
        elif "Public" in acc_text:
            access_param = "public"
        elif "Verrouillé" in acc_text:
            access_param = "locked"

        sort_param = "az" if "A-Z" in filter_state["sort"] else "recent"

        status_param = None
        stat_text = filter_state["status"]
        if "Déjà installés" in stat_text:
            status_param = "installed"
        elif "Non installés" in stat_text:
            status_param = "not_installed"
        elif "Mises à jour" in stat_text:
            status_param = "updates_available"

        try:
            # Query auth status for badges
            accounts = self.api_client.get_accounts()
            is_patreon_auth = any(a.get("provider_name") == "patreon" and a.get("is_member") for a in accounts)
            is_loverslab_auth = any(a.get("provider_name") == "loverslab" and a.get("is_member") for a in accounts)

            # Query catalog from API with pagination
            res = self.api_client.get_catalog(
                search=filter_state["search"] or None,
                source=source_param,
                access=access_param,
                status=status_param,
                sort=sort_param,
                page=self.current_page,
                limit=self.page_size,
            )
            items = res.get("items", [])
            self.total_items = res.get("total", 0)
            self.total_pages = max(1, math.ceil(self.total_items / self.page_size))

            # Update pagination controls
            self.btn_prev.setEnabled(self.current_page > 1)
            self.btn_next.setEnabled(self.current_page < self.total_pages)
            self.lbl_page_info.setText(
                f"Page {self.current_page} sur {self.total_pages}  ({self.total_items} mod{'s' if self.total_items > 1 else ''} indexé{'s' if self.total_items > 1 else ''})"
            )

            # Clear existing items
            while self.grid_layout.count():
                item = self.grid_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not items:
                no_data = QLabel("Catalogue en cours de chargement ou aucun mod ne correspond aux filtres.")
                no_data.setStyleSheet("font-size: 14px; color: #64748b; padding: 40px;")
                no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.grid_layout.addWidget(no_data, 0, 0)
                return

            columns = 4
            row = 0
            col = 0

            for m in items:
                mod_dict = {
                    "id": m["id"],
                    "source": m["source"],
                    "remote_id": m["remote_id"],
                    "title": m["title"],
                    "author": m["author"],
                    "page_url": m["page_url"],
                    "thumbnail_url": m["thumbnail_url"],
                    "updated_date": m["updated_date"],
                    "patreon_status": m["patreon_status"],
                    "patreon_tier": m["patreon_tier"],
                    "external_links": [],
                    "download_urls": [],
                }

                card = ModCard(
                    mod_dict,
                    is_installed=m.get("is_installed", False),
                    has_update=m.get("has_update", False),
                    is_patreon_auth=is_patreon_auth,
                    is_loverslab_auth=is_loverslab_auth,
                )
                card.install_requested.connect(self.install_mod)
                card.details_requested.connect(
                    lambda d, inst=m.get("is_installed", False): self._show_mod_details(d, inst)
                )
                self.grid_layout.addWidget(card, row, col)

                col += 1
                if col >= columns:
                    col = 0
                    row += 1

        except Exception as e:
            logger.error(f"Erreur API lors du rafraîchissement du catalogue: {e}")

    def _style_toggle_button(self, state: str):
        """Styles the persistent right-edge status tab based on state (OK, RUNNING, ERROR)."""
        if state == "RUNNING":
            self.btn_toggle_drawer.setStyleSheet("""
                QPushButton {
                    background-color: #1e1b4b;
                    color: #93c5fd;
                    border: 1px solid #3b82f6;
                    border-radius: 8px;
                    padding: 4px 8px;
                    font-weight: 700;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #2e2870; }
            """)
        elif state == "ERROR":
            self.btn_toggle_drawer.setStyleSheet("""
                QPushButton {
                    background-color: #450a0a;
                    color: #fca5a5;
                    border: 1px solid #dc2626;
                    border-radius: 8px;
                    padding: 4px 8px;
                    font-weight: 700;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #5c0f0f; }
            """)
        else:  # OK
            self.btn_toggle_drawer.setStyleSheet("""
                QPushButton {
                    background-color: #064e3b;
                    color: #a7f3d0;
                    border: 1px solid #059669;
                    border-radius: 8px;
                    padding: 4px 8px;
                    font-weight: 700;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #0d6951; }
            """)

    def _style_site_tab_pill(self, label: QLabel, state: str, text: str):
        """Styles an individual site badge on the persistent edge tab."""
        label.setText(text)
        if state == "RUNNING":
            label.setStyleSheet("""
                background-color: #1e1b4b;
                color: #93c5fd;
                border: 1px solid #3b82f6;
                border-radius: 6px;
                padding: 4px;
                font-size: 10px;
                font-weight: 700;
            """)
        elif state == "ERROR":
            label.setStyleSheet("""
                background-color: #450a0a;
                color: #fca5a5;
                border: 1px solid #dc2626;
                border-radius: 6px;
                padding: 4px;
                font-size: 10px;
                font-weight: 700;
            """)
        else:  # OK
            label.setStyleSheet("""
                background-color: #064e3b;
                color: #a7f3d0;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 4px;
                font-size: 10px;
                font-weight: 700;
            """)

    def _style_resync_button(self, loading: bool = False):
        if loading:
            self.btn_resync.setStyleSheet("""
                QPushButton {
                    background-color: #312e81;
                    color: #a5b4fc;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 11px;
                }
            """)
        else:
            self.btn_resync.setStyleSheet("""
                QPushButton {
                    background-color: #4f46e5;
                    color: #ffffff;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #4338ca; }
                QPushButton:disabled { background-color: #1e1b4b; color: #6366f1; }
            """)

    def _toggle_loverslab_section(self):
        """Collapses or expands the LoversLab provider card."""
        self._ll_is_expanded = not self._ll_is_expanded
        self.btn_collapse_ll.setText("▼" if self._ll_is_expanded else "▲")
        self.ll_expanded_details.setVisible(self._ll_is_expanded)
        self.ll_collapsed_summary.setVisible(not self._ll_is_expanded)

    def _init_subcategory_rows(self):
        """Initializes the 14 subcategories rows in the drawer with default estimates."""
        categories = [
            ("174", "WickedWhims", 16),
            ("201", "Animations - WW", 7),
            ("215", "Translations - WW", 5),
            ("202", "Animations - Other", 7),
            ("200", "Extensions", 3),
            ("203", "Clothing", 128),
            ("204", "Accessories & Makeup", 16),
            ("205", "Body Parts", 12),
            ("206", "Objects", 86),
            ("404", "Paintings & Posters", 14),
            ("207", "Lots", 18),
            ("209", "Translations", 35),
            ("210", "Other", 23),
            ("216", "Uncategorized", 27),
        ]
        for cid, cname, def_p in categories:
            row_frame = QFrame()
            row_frame.setStyleSheet("background-color: #0e1224; border-radius: 4px;")
            r_layout = QHBoxLayout(row_frame)
            r_layout.setContentsMargins(4, 2, 4, 2)
            r_layout.setSpacing(6)

            lbl_icon = QLabel("⏳")
            lbl_icon.setFixedWidth(16)
            r_layout.addWidget(lbl_icon)

            lbl_name = QLabel(cname)
            lbl_name.setStyleSheet("font-size: 10px; color: #cbd5e1; font-weight: 600;")
            r_layout.addWidget(lbl_name, stretch=1)

            lbl_detail = QLabel(f"0/{def_p} p.")
            lbl_detail.setStyleSheet("font-size: 9px; color: #64748b;")
            r_layout.addWidget(lbl_detail)

            self.subcats_layout.addWidget(row_frame)
            self.subcat_rows[cid] = (lbl_icon, lbl_name, lbl_detail)

    def _toggle_drawer(self):
        """Toggles the visibility of the retractable scraping status drawer."""
        new_vis = not self.drawer_panel.isVisible()
        self.drawer_panel.setVisible(new_vis)
        arrow = "▶" if new_vis else "◀"
        cur_t = self.btn_toggle_drawer.text()
        parts = cur_t.rsplit(" ", 1)
        base = parts[0] if len(parts) > 1 else cur_t
        self.btn_toggle_drawer.setText(f"{base} {arrow}")

    def start_sync(self, max_pages: int = 0):
        """Starts background synchronization with instantaneous UI response (<1ms) via QThread."""
        self.btn_resync.setEnabled(False)
        self.btn_resync.setText("⏳ Démarrage en cours...")
        self._style_resync_button(loading=True)
        self.tab_loverslab_pill.setText("LoversLab 🔵...")
        self._style_site_tab_pill(self.tab_loverslab_pill, "RUNNING", "LoversLab 🔵...")
        self.sync_banner.setVisible(True)
        self.sync_banner_lbl.setText("🔄 Lancement de la synchronisation en arrière-plan...")

        self._page1_displayed = False
        self._last_pages_completed = 0

        self._sync_worker = SyncTriggerWorker(self.api_client, max_pages=max_pages)
        self._sync_worker.finished_signal.connect(self._on_sync_triggered)
        self._sync_worker.start()
        self.start_sync_monitoring()

    def _on_sync_triggered(self, success: bool, message: str):
        if not success:
            QMessageBox.warning(self, "Erreur", f"Impossible de lancer la synchronisation : {message}")
            self.btn_resync.setEnabled(True)
            self.btn_resync.setText("🔄 Relancer LoversLab")
            self._style_resync_button()

    def start_sync_monitoring(self):
        """Ensures timer is active to monitor sync status."""
        if not self.monitor_timer.isActive():
            self.monitor_timer.start()

    def _check_sync_status(self):
        """Polls API for background synchronization updates and updates drawer & persistent tab."""
        try:
            status = self.api_client.get_catalog_sync_status()
            is_running = status.get("is_running", False)
            pct = status.get("progress_percent", 0)
            msg = status.get("message", "Synchronisation...")
            pages_done = status.get("pages_completed", 0)
            total_pages = status.get("total_pages", 0)
            cur_cat = status.get("current_category") or "Prêt"
            has_error = status.get("has_error", False)
            err_msg = status.get("error_message") or ""
            page1_ready = status.get("page1_ready", False)
            total_scraped = status.get("total_scraped", 0)
            last_completed = status.get("last_completed_at") or ""
            categories_progress = status.get("categories_progress", [])

            arrow = "▶" if self.drawer_panel.isVisible() else "◀"

            # 1. Update Persistent Right-edge Tab
            if has_error:
                self.btn_toggle_drawer.setText(f"🔴 Sites {arrow}")
                self._style_toggle_button("ERROR")
                self._style_site_tab_pill(self.tab_loverslab_pill, "ERROR", "LoversLab 🔴")
            elif is_running:
                self.btn_toggle_drawer.setText(f"🔵 Sites ({pct}%) {arrow}")
                self._style_toggle_button("RUNNING")
                self._style_site_tab_pill(self.tab_loverslab_pill, "RUNNING", f"LoversLab 🔵 {pct}%")
            else:
                self.btn_toggle_drawer.setText(f"🛰️ Sites {arrow}")
                self._style_toggle_button("OK")
                self._style_site_tab_pill(self.tab_loverslab_pill, "OK", "LoversLab 🟢")

            # 2. Update LoversLab Accordion Header Pill
            if has_error:
                self.drawer_status_pill.setText("🔴 Erreur")
                self.drawer_status_pill.setStyleSheet(
                    "background-color: #450a0a; color: #fca5a5; border: 1px solid #dc2626; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 700;"
                )
            elif is_running:
                self.drawer_status_pill.setText(f"🔵 En cours ({pct}%)")
                self.drawer_status_pill.setStyleSheet(
                    "background-color: #1e1b4b; color: #93c5fd; border: 1px solid #3b82f6; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 700;"
                )
            else:
                self.drawer_status_pill.setText("🟢 Prêt / Terminé")
                self.drawer_status_pill.setStyleSheet(
                    "background-color: #064e3b; color: #a7f3d0; border: 1px solid #059669; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: 700;"
                )

            # 3. Update Collapsed Summary
            self.ll_collapsed_summary_lbl.setText(
                f"14 sous-catégories • {total_scraped} mods indexés • p.{pages_done}/{total_pages}"
            )

            # 4. Update Expanded Details
            self.drawer_progress_bar.setValue(pct)
            if total_pages > 0:
                self.drawer_lbl_progress.setText(f"📄 Progression : Page {pages_done} / {total_pages} ({pct}%)")
            else:
                self.drawer_lbl_progress.setText(f"📄 Progression : Page {pages_done}")
            self.drawer_lbl_category.setText(f"📂 En cours : {cur_cat}")
            self.drawer_lbl_mods.setText(f"📦 Mods indexés : {total_scraped}")
            if last_completed:
                date_part = last_completed.replace("T", " ")[:19]
                self.drawer_lbl_last_sync.setText(f"🕒 Dernier scan : {date_part}")

            # 5. Update Subcategory Rows
            for cat_item in categories_progress:
                cid = str(cat_item.get("id"))
                if cid in self.subcat_rows:
                    lbl_icon, lbl_name, lbl_detail = self.subcat_rows[cid]
                    c_stat = cat_item.get("status", "PENDING")
                    c_done = cat_item.get("pages_completed", 0)
                    c_total = cat_item.get("total_pages", 0)
                    c_mods = cat_item.get("mods_count", 0)

                    if c_stat == "COMPLETED":
                        lbl_icon.setText("🟢")
                        lbl_detail.setText(f"{c_done}/{c_total} p. ({c_mods} mods)")
                        lbl_detail.setStyleSheet("font-size: 9px; color: #a7f3d0; font-weight: 600;")
                    elif c_stat == "IN_PROGRESS":
                        lbl_icon.setText("🔵")
                        lbl_detail.setText(f"p. {c_done}/{c_total} ({c_mods} mods)")
                        lbl_detail.setStyleSheet("font-size: 9px; color: #93c5fd; font-weight: 600;")
                    elif c_stat == "ERROR":
                        lbl_icon.setText("🔴")
                        lbl_detail.setText("Erreur")
                        lbl_detail.setStyleSheet("font-size: 9px; color: #fca5a5;")
                    else:
                        lbl_icon.setText("⏳")
                        lbl_detail.setText(f"Attente ({c_total} p.)")
                        lbl_detail.setStyleSheet("font-size: 9px; color: #64748b;")

            # 6. Resync Button State & Banner
            if is_running:
                self.btn_resync.setEnabled(False)
                self.btn_resync.setText("⏳ Scraping en cours...")
                self._style_resync_button(loading=True)
                self.sync_banner.setVisible(True)
                self.sync_banner_lbl.setText(f"🔄 {msg}")
                self.sync_bar.setValue(pct)

                if page1_ready and not self._page1_displayed:
                    self._page1_displayed = True
                    self._last_pages_completed = pages_done
                    self.refresh_catalog()
                elif pages_done > self._last_pages_completed:
                    self._last_pages_completed = pages_done
                    self.refresh_catalog()
            elif has_error:
                self.btn_resync.setEnabled(True)
                self.btn_resync.setText("🔄 Relancer LoversLab")
                self._style_resync_button()
                self.sync_banner.setVisible(True)
                self.sync_banner_lbl.setText(f"⚠️ Erreur scraping : {err_msg or msg}")
            else:
                self.btn_resync.setEnabled(True)
                self.btn_resync.setText("🔄 Relancer LoversLab")
                self._style_resync_button()
                self.sync_banner.setVisible(False)
                if self._last_pages_completed > 0:
                    self._last_pages_completed = 0
                    self.refresh_catalog()

        except Exception as e:
            logger.debug(f"Erreur lors de la vérification du statut de sync: {e}")

    def install_mod(self, mod_data: dict):
        """Starts background download and installation of selected mod via API after dependency validation."""
        # 1. Dependency check
        try:
            chk = self.api_client.check_dependencies({
                "catalog_mod_id": mod_data.get("id"),
                "source": mod_data.get("source", "loverslab"),
                "remote_id": str(mod_data.get("remote_id", "")),
                "page_url": mod_data.get("page_url"),
                "title": mod_data.get("title"),
            })
        except Exception as e:
            logger.debug(f"Erreur vérification dépendances: {e}")
            chk = {"can_install": True, "missing_dependencies": [], "unfound_dependencies": [], "is_partial": False}

        missing = chk.get("missing_dependencies", [])
        already = chk.get("already_installed_dependencies", [])
        unfound = chk.get("unfound_dependencies", [])
        is_partial = chk.get("is_partial", False) or bool(unfound)

        if not chk.get("can_install", True) and not is_partial:
            reason = chk.get(
                "blocking_reason",
                "Ce mod requiert des dépendances non identifiées sur LoversLab. Installation impossible.",
            )
            QMessageBox.warning(self, "Installation Bloquée", reason)
            return

        if missing or unfound or is_partial:
            mod_title = mod_data.get("title", "ce mod")
            dlg = DependenciesDialog(
                mod_title,
                already,
                missing,
                unfound=unfound,
                is_partial=is_partial,
                parent=self,
            )
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return

        # 2. Proceed with installation
        self.progress_dlg = ProgressDialog(f"Installation de {mod_data.get('title')}", self)
        self.progress_dlg.show()

        self.install_worker = InstallWorker(mod_data)
        self.install_worker.progress.connect(self._on_install_progress)
        self.install_worker.finished.connect(self._on_install_finished)
        self.install_worker.start()

    def _on_install_progress(self, percent: int, status: str, details: str = ""):
        if hasattr(self, "progress_dlg") and self.progress_dlg.isVisible():
            self.progress_dlg.update_progress(percent, status, details)

    def _on_install_finished(self, success: bool, msg: str):
        if hasattr(self, "progress_dlg"):
            self.progress_dlg.close()
        if success:
            QMessageBox.information(self, "Installation Réussie", msg)
        else:
            QMessageBox.warning(self, "Erreur d'Installation", msg)
        self.refresh_catalog()
        self.install_finished.emit(success, msg)

    def _show_mod_details(self, mod_data: dict, is_installed: bool = False):
        """Emits details_requested signal to switch to full-page ModDetailView."""
        data_copy = dict(mod_data)
        data_copy["is_installed"] = is_installed
        self.details_requested.emit(data_copy)
