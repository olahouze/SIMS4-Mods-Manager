import math
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QLabel,
    QPushButton,
    QFrame,
    QProgressBar,
    QMessageBox,
    QDialog,
)
from PySide6.QtCore import Qt, Signal, QTimer

from src.api.client import get_api_client
from src.ui.components.filter_bar import FilterBar
from src.ui.components.mod_card import ModCard
from src.ui.components.responsive_card_grid import ResponsiveCardGrid
from src.ui.components.dependencies_dialog import DependenciesDialog
from src.ui.components.progress_dialog import ProgressDialog
from src.ui.components.provider_drawer import ProviderDrawer
from src.ui.workers.catalog_workers import SyncTriggerWorker, InstallWorker, CatalogFetchWorker
from src.i18n import tr
from src.utils.logger import logger



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
        self._fetch_worker = None
        self._fetch_id = 0

        self.IDLE_MONITOR_INTERVAL_MS = 4000
        self.ACTIVE_MONITOR_INTERVAL_MS = 1200

        # Background sync monitoring timer with adaptive back-off
        self.monitor_timer = QTimer(self)
        self.monitor_timer.setInterval(self.IDLE_MONITOR_INTERVAL_MS)
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
        self.title_lbl = QLabel(tr("catalog.title"))
        self.title_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(self.title_lbl)

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

        self.sync_banner_lbl = QLabel(tr("catalog.sync_running"))
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
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("background-color: transparent; border: none;")

        self.card_grid = ResponsiveCardGrid(min_card_width=295, spacing=16)
        self.scroll_area.setWidget(self.card_grid)
        layout.addWidget(self.scroll_area, stretch=1)

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

        self.btn_prev = QPushButton(f"◀ {tr('dialogs.previous', default='Précédent')}")
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

        self.lbl_page_info = QLabel(tr("catalog.page_info", current=1, total=1, total_items=0))
        self.lbl_page_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_page_info.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 600;")
        p_layout.addWidget(self.lbl_page_info, stretch=1)

        self.btn_next = QPushButton(f"{tr('dialogs.next', default='Suivant')} ▶")
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

        # Right Column: Modular Persistent Status Tab + Retractable Drawer with Pause/Stop/Resume Controls
        self.provider_drawer = ProviderDrawer(self)
        self.provider_drawer.start_requested.connect(lambda prov: self.start_sync(max_pages=0))
        self.provider_drawer.pause_requested.connect(self._on_pause_sync)
        self.provider_drawer.resume_requested.connect(self._on_resume_sync)
        self.provider_drawer.stop_requested.connect(self._on_stop_sync)
        main_h_layout.addWidget(self.provider_drawer)


        # Initial data load
        self.refresh_catalog()

        # Check sync status immediately on startup
        self._check_sync_status()

    def _on_filters_changed(self):
        """Reset to page 1 when user changes search query or filters."""
        self.current_page = 1
        self.refresh_catalog()
        if hasattr(self, "scroll_area"):
            self.scroll_area.verticalScrollBar().setValue(0)

    def _on_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_catalog()
            if hasattr(self, "scroll_area"):
                self.scroll_area.verticalScrollBar().setValue(0)

    def _on_next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.refresh_catalog()
            if hasattr(self, "scroll_area"):
                self.scroll_area.verticalScrollBar().setValue(0)

    def refresh_catalog(self):
        """Clears and re-populates the catalog grid with filtered and paginated items from API."""
        filter_state = self.filter_bar.get_filter_state()

        source_param = None
        if filter_state["source"] == "LoversLab":
            source_param = "loverslab"
        elif filter_state["source"] == "Patreon":
            source_param = "patreon"

        type_param = filter_state.get("mod_type")
        if type_param == "all":
            type_param = None

        access_param = None
        acc_text = str(filter_state.get("access", ""))
        if acc_text in ("direct", "needs_account", "needs_sub", "unlocked", "public", "locked"):
            access_param = acc_text
        elif "Directement" in acc_text:
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

        sort_val = str(filter_state.get("sort", ""))
        sort_param = "az" if ("A-Z" in sort_val or sort_val == "az") else "recent"

        status_param = None
        stat_text = str(filter_state.get("status", ""))
        if stat_text in ("installed", "not_installed", "updates_available"):
            status_param = stat_text
        elif "Déjà installés" in stat_text:
            status_param = "installed"
        elif "Non installés" in stat_text:
            status_param = "not_installed"
        elif "Mises à jour" in stat_text:
            status_param = "updates_available"

        params = {
            "search": filter_state["search"] or None,
            "source": source_param,
            "access": access_param,
            "status": status_param,
            "mod_type": type_param,
            "sort": sort_param,
            "page": self.current_page,
            "limit": self.page_size,
        }

        # Cancel previous background fetch if active
        if self._fetch_worker and self._fetch_worker.isRunning():
            try:
                self._fetch_worker.data_ready.disconnect()
                self._fetch_worker.error_signal.disconnect()
            except Exception:
                pass
            self._fetch_worker.terminate()
            self._fetch_worker = None

        self._fetch_id += 1
        self._fetch_worker = CatalogFetchWorker(self.api_client, params, fetch_id=self._fetch_id)
        self._fetch_worker.data_ready.connect(self._on_catalog_data_ready)
        self._fetch_worker.error_signal.connect(self._on_catalog_fetch_error)
        self._fetch_worker.start()

    def _on_catalog_data_ready(self, res: dict, accounts: list, fetch_id: int):
        if fetch_id != self._fetch_id:
            return

        is_patreon_auth = any(a.get("provider_name") == "patreon" and a.get("is_member") for a in accounts)
        is_loverslab_auth = any(a.get("provider_name") == "loverslab" and a.get("is_member") for a in accounts)

        items = res.get("items", [])
        self.total_items = res.get("total", 0)
        self.total_pages = max(1, math.ceil(self.total_items / self.page_size))

        # Update pagination controls
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < self.total_pages)
        self.lbl_page_info.setText(
            tr("catalog.page_info", current=self.current_page, total=self.total_pages, total_items=self.total_items)
        )

        if not items:
            self.card_grid.set_empty_message(tr("catalog.empty_desc"))
            return

        new_cards = []
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
                "requirements_text": m.get("requirements_text"),
                "requirements_status": m.get("requirements_status", "NONE"),
                "dependencies": m.get("dependencies", []),
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
            new_cards.append(card)

        self.card_grid.set_cards(new_cards)

    def _on_catalog_fetch_error(self, error_msg: str, fetch_id: int):
        if fetch_id != self._fetch_id:
            return
        logger.error(f"Erreur API lors du rafraîchissement du catalogue: {error_msg}")

    def _on_pause_sync(self, provider: str = "loverslab"):
        try:
            self.api_client.pause_catalog_sync(provider)
            self._check_sync_status()
        except Exception as e:
            logger.error(f"Erreur mise en pause {provider}: {e}")

    def _on_resume_sync(self, provider: str = "loverslab"):
        try:
            self.api_client.resume_catalog_sync(provider)
            self._check_sync_status()
        except Exception as e:
            logger.error(f"Erreur reprise {provider}: {e}")

    def _on_stop_sync(self, provider: str = "loverslab"):
        try:
            self.api_client.stop_catalog_sync(provider)
            self._check_sync_status()
        except Exception as e:
            logger.error(f"Erreur arrêt {provider}: {e}")

    def start_sync(self, max_pages: int = 0):
        """Starts background synchronization with instantaneous UI response (<1ms) via QThread."""
        self.sync_banner.setVisible(True)
        self.sync_banner_lbl.setText("🔄 Lancement de la synchronisation en arrière-plan...")

        self._page1_displayed = False
        self._last_pages_completed = 0

        self._sync_worker = SyncTriggerWorker(self.api_client, max_pages=max_pages)
        self._sync_worker.finished_signal.connect(self._on_sync_triggered)
        self._sync_worker.start()
        self.monitor_timer.setInterval(self.ACTIVE_MONITOR_INTERVAL_MS)
        self.start_sync_monitoring()

    def _on_sync_triggered(self, success: bool, message: str):
        if not success:
            QMessageBox.warning(self, tr("dialogs.error_title"), f"{message}")
            self._check_sync_status()

    def start_sync_monitoring(self):
        """Ensures timer is active to monitor sync status."""
        if not self.monitor_timer.isActive():
            self.monitor_timer.start()

    def _check_sync_status(self):
        """Polls API for background synchronization updates and updates drawer & persistent tab."""
        try:
            status = self.api_client.get_catalog_sync_status()
            is_running = status.get("is_running", False)
            is_paused = status.get("is_paused", False)
            pct = status.get("progress_percent", 0)
            msg = status.get("message", "Synchronisation...")
            pages_done = status.get("pages_completed", 0)
            has_error = status.get("has_error", False)
            err_msg = status.get("error_message") or ""
            page1_ready = status.get("page1_ready", False)

            # Delegate satellite drawer updates to ProviderDrawer
            self.provider_drawer.update_sync_status(status)

            if is_running:
                if self.monitor_timer.interval() != self.ACTIVE_MONITOR_INTERVAL_MS:
                    self.monitor_timer.setInterval(self.ACTIVE_MONITOR_INTERVAL_MS)
                self.sync_banner.setVisible(True)
                if is_paused:
                    self.sync_banner_lbl.setText(f"⏸️ {msg}")
                else:
                    self.sync_banner_lbl.setText(f"🔄 {msg}")
                self.sync_bar.setValue(pct)

                if page1_ready and not self._page1_displayed:
                    self._page1_displayed = True
                    self._last_pages_completed = pages_done
                    self.refresh_catalog()
                elif pages_done > self._last_pages_completed:
                    self._last_pages_completed = pages_done
            elif has_error:
                if self.monitor_timer.interval() != self.IDLE_MONITOR_INTERVAL_MS:
                    self.monitor_timer.setInterval(self.IDLE_MONITOR_INTERVAL_MS)
                self.sync_banner.setVisible(True)
                self.sync_banner_lbl.setText(f"⚠️ Erreur scraping : {err_msg or msg}")
            else:
                if self.monitor_timer.interval() != self.IDLE_MONITOR_INTERVAL_MS:
                    self.monitor_timer.setInterval(self.IDLE_MONITOR_INTERVAL_MS)
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
        comments = chk.get("comment_dependencies", [])
        game_dlcs = chk.get("game_dlc_dependencies", [])
        is_partial = chk.get("is_partial", False) or bool(unfound)

        if not chk.get("can_install", True) and not is_partial:
            reason = chk.get(
                "blocking_reason",
                tr("catalog.install_blocked_reason"),
            )
            QMessageBox.warning(self, tr("catalog.install_blocked_title"), reason)
            return

        if missing or unfound or comments or is_partial or game_dlcs:
            mod_title = mod_data.get("title", tr("common.untitled"))
            dlg = DependenciesDialog(
                mod_title,
                already,
                missing,
                unfound=list(unfound) + list(comments),
                is_partial=is_partial,
                game_dlcs=game_dlcs,
                mod_data=mod_data,
                parent=self,
            )
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return


        # 2. Proceed with installation
        self.progress_dlg = ProgressDialog(tr("catalog.install_progress_title", title=mod_data.get('title', '')), self)
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
            QMessageBox.information(self, tr("catalog.install_success_title"), msg)
        else:
            QMessageBox.warning(self, tr("catalog.install_error_title"), msg)
        self.refresh_catalog()
        self.install_finished.emit(success, msg)

    def _show_mod_details(self, mod_data: dict, is_installed: bool = False):
        """Emits details_requested signal to switch to full-page ModDetailView."""
        data_copy = dict(mod_data)
        data_copy["is_installed"] = is_installed
        self.details_requested.emit(data_copy)

    def retranslate_ui(self):
        """Retranslates all text elements in CatalogView."""
        self.title_lbl.setText(tr("catalog.title"))
        self.sync_banner_lbl.setText(tr("catalog.sync_running"))
        self.btn_prev.setText(tr("image_viewer.btn_prev"))
        self.btn_next.setText(tr("image_viewer.btn_next"))
        if hasattr(self.filter_bar, "retranslate_ui"):
            self.filter_bar.retranslate_ui()
        if hasattr(self.provider_drawer, "retranslate_ui"):
            self.provider_drawer.retranslate_ui()
        self.lbl_page_info.setText(
            tr("catalog.page_info", current=self.current_page, total=self.total_pages, total_items=self.total_items)
        )
        self.refresh_catalog()
