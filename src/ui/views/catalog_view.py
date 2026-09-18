import math
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QLabel,
    QPushButton,
    QFrame,
    QMessageBox,
    QDialog,
)
from PySide6.QtCore import Signal, QTimer

from src.api.client import get_api_client
from src.ui.components.filter_bar import FilterBar
from src.ui.components.mod_card import ModCard
from src.ui.components.responsive_card_grid import ResponsiveCardGrid
from src.ui.components.dependencies_dialog import DependenciesDialog
from src.ui.components.provider_drawer import ProviderDrawer
from src.ui.workers.catalog_workers import SyncTriggerWorker, CatalogFetchWorker
from src.ui.views.catalog.filter_adapter import build_catalog_api_params
from src.ui.views.catalog.catalog_widgets import CatalogSyncBannerWidget, CatalogPaginationBar
from src.i18n import tr
from src.utils.logger import logger
from src.utils.thread_utils import safe_stop_thread


class CatalogView(QWidget):
    """
    Unified multi-source mod catalog view with grid layout, search/filter bar,
    progressive page-1 immediate rendering, background sync monitoring, and pagination.
    """

    details_requested = Signal(dict)
    download_requested = Signal(dict)
    view_downloads_requested = Signal()
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

        self.IDLE_MONITOR_INTERVAL_MS = 8000
        self.ACTIVE_MONITOR_INTERVAL_MS = 1200

        self.monitor_timer = QTimer(self)
        self.monitor_timer.setInterval(self.IDLE_MONITOR_INTERVAL_MS)
        self.monitor_timer.timeout.connect(self._check_sync_status)
        self.monitor_timer.start()

        self.init_ui()

    def init_ui(self):
        main_h_layout = QHBoxLayout(self)
        main_h_layout.setContentsMargins(18, 18, 18, 18)
        main_h_layout.setSpacing(12)

        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.title_lbl = QLabel(tr("catalog.title"))
        self.title_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(self.title_lbl)

        # Sync Banner Widget
        self.sync_banner_widget = CatalogSyncBannerWidget(self)
        layout.addWidget(self.sync_banner_widget)

        self.filter_bar = FilterBar()
        self.filter_bar.filters_changed.connect(self._on_filters_changed)
        layout.addWidget(self.filter_bar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: transparent; border: none;")

        self.card_grid = ResponsiveCardGrid()
        self.scroll_area.setWidget(self.card_grid)
        layout.addWidget(self.scroll_area)

        # Pagination Bar
        self.pagination_bar = CatalogPaginationBar(self)
        self.pagination_bar.prev_requested.connect(self._on_prev_page)
        self.pagination_bar.next_requested.connect(self._on_next_page)
        layout.addWidget(self.pagination_bar)

        # Non-intrusive Download Notification Banner
        self.toast_banner = QFrame(self)
        self.toast_banner.setObjectName("DownloadToast")
        self.toast_banner.setStyleSheet("""
            QFrame#DownloadToast {
                background-color: #0f172a;
                border: 1px solid #0284c7;
                border-radius: 10px;
            }
        """)
        toast_layout = QHBoxLayout(self.toast_banner)
        toast_layout.setContentsMargins(14, 8, 14, 8)
        toast_layout.setSpacing(12)

        self.toast_label = QLabel()
        self.toast_label.setStyleSheet("color: #f8fafc; font-size: 13px; font-weight: 600;")
        toast_layout.addWidget(self.toast_label, stretch=1)

        self.btn_toast_view = QPushButton(tr("downloads.toast_action_view"))
        self.btn_toast_view.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        self.btn_toast_view.clicked.connect(self.view_downloads_requested.emit)
        toast_layout.addWidget(self.btn_toast_view)

        btn_toast_close = QPushButton("✕")
        btn_toast_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: none;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover { color: #f8fafc; }
        """)
        btn_toast_close.clicked.connect(lambda: self.toast_banner.setVisible(False))
        toast_layout.addWidget(btn_toast_close)

        self.toast_banner.setVisible(False)
        layout.addWidget(self.toast_banner)

        main_h_layout.addWidget(left_widget, stretch=1)

        # Satellite Provider Drawer
        self.provider_drawer = ProviderDrawer(self)
        self.provider_drawer.start_requested.connect(lambda p: self.start_sync(max_pages=0))
        self.provider_drawer.pause_requested.connect(self._on_pause_sync)
        self.provider_drawer.resume_requested.connect(self._on_resume_sync)
        self.provider_drawer.stop_requested.connect(self._on_stop_sync)
        main_h_layout.addWidget(self.provider_drawer)

        self.refresh_catalog()
        self._check_sync_status()

    # Backward compatible attributes
    @property
    def sync_banner(self):
        return self.sync_banner_widget

    @property
    def sync_banner_lbl(self):
        return self.sync_banner_widget.sync_banner_lbl

    @property
    def sync_bar(self):
        return self.sync_banner_widget.sync_bar

    @property
    def btn_prev(self):
        return self.pagination_bar.btn_prev

    @property
    def btn_next(self):
        return self.pagination_bar.btn_next

    @property
    def lbl_page_info(self):
        return self.pagination_bar.lbl_page_info

    def _on_filters_changed(self):
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
        filter_state = self.filter_bar.get_filter_state()
        params = build_catalog_api_params(filter_state, self.current_page, self.page_size)

        if self._fetch_worker is not None:
            safe_stop_thread(self._fetch_worker)
            self._fetch_worker = None

        self._fetch_id += 1
        self._fetch_worker = CatalogFetchWorker(self.api_client, params, fetch_id=self._fetch_id)
        self._fetch_worker.data_ready.connect(self._on_catalog_data_ready)
        self._fetch_worker.error_signal.connect(self._on_catalog_fetch_error)
        self._fetch_worker.start()

    def _on_catalog_data_ready(self, res: dict, accounts: list, fetch_id: int):
        if fetch_id != self._fetch_id:
            return
        self._fetch_worker = None

        is_patreon_auth = any(a.get("provider_name") == "patreon" and a.get("is_member") for a in accounts)
        is_loverslab_auth = any(a.get("provider_name") == "loverslab" and a.get("is_member") for a in accounts)

        items = res.get("items", [])
        self.total_items = res.get("total", 0)
        self.total_pages = max(1, math.ceil(self.total_items / self.page_size))
        self.pagination_bar.update_pagination(self.current_page, self.total_pages, self.total_items)

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
        self._fetch_worker = None
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
        self.sync_banner_widget.set_running("Lancement de la synchronisation en arrière-plan...", 0)
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
        if not self.monitor_timer.isActive():
            self.monitor_timer.start()

    def _check_sync_status(self):
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

            self.provider_drawer.update_sync_status(status)

            if is_running:
                if self.monitor_timer.interval() != self.ACTIVE_MONITOR_INTERVAL_MS:
                    self.monitor_timer.setInterval(self.ACTIVE_MONITOR_INTERVAL_MS)
                self.sync_banner_widget.set_running(msg, pct, is_paused=is_paused)

                if page1_ready and not self._page1_displayed:
                    self._page1_displayed = True
                    self._last_pages_completed = pages_done
                    self.refresh_catalog()
                elif pages_done > self._last_pages_completed:
                    self._last_pages_completed = pages_done
                    if self.current_page == 1 and not is_paused:
                        self.refresh_catalog()
            elif has_error:
                if self.monitor_timer.interval() != self.IDLE_MONITOR_INTERVAL_MS:
                    self.monitor_timer.setInterval(self.IDLE_MONITOR_INTERVAL_MS)
                self.sync_banner_widget.set_error(err_msg or msg)
            else:
                if self.monitor_timer.interval() != self.IDLE_MONITOR_INTERVAL_MS:
                    self.monitor_timer.setInterval(self.IDLE_MONITOR_INTERVAL_MS)
                self.sync_banner_widget.set_idle()
                if self._last_pages_completed > 0 or not self._page1_displayed:
                    self._last_pages_completed = 0
                    self._page1_displayed = True
                    self.refresh_catalog()

        except Exception as e:
            logger.debug(f"Erreur vérification statut sync: {e}")

    def install_mod(self, mod_data: dict):
        mod_id = mod_data.get("id")
        try:
            payload = {
                "catalog_mod_id": mod_id,
                "source": mod_data.get("source", "loverslab"),
                "remote_id": mod_data.get("remote_id"),
                "page_url": mod_data.get("page_url"),
                "title": mod_data.get("title"),
            }
            dep_res = self.api_client.check_dependencies(payload)
            al_inst = dep_res.get("already_installed_dependencies") or dep_res.get("already_installed") or []
            missing = dep_res.get("missing_dependencies") or dep_res.get("missing") or []
            unfound = dep_res.get("unfound_dependencies") or dep_res.get("unfound") or []
            dlcs = dep_res.get("game_dlc_dependencies") or dep_res.get("game_dlcs") or []
            if dep_res and (missing or al_inst or dlcs or unfound):
                dlg = DependenciesDialog(
                    mod_title=dep_res.get("mod_title", mod_data.get("title", "")),
                    already_installed=al_inst,
                    missing=missing,
                    unfound=unfound,
                    is_partial=dep_res.get("is_partial", False),
                    game_dlcs=dlcs,
                    mod_data=mod_data,
                    parent=self,
                )
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return
        except Exception as e:
            logger.warning(f"Impossible de vérifier les dépendances avant installation: {e}")

        # Emit download request for dedicated downloads tab (non-blocking)
        self.download_requested.emit(mod_data)

        # Show non-intrusive toast banner allowing user to continue browsing the catalog
        title = mod_data.get("title") or "Mod"
        if hasattr(self, "toast_banner"):
            self.toast_label.setText(tr("downloads.toast_started", title=title))
            self.toast_banner.setVisible(True)
            QTimer.singleShot(6000, lambda: self.toast_banner.setVisible(False))

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
        data_copy = dict(mod_data)
        data_copy["is_installed"] = is_installed
        self.details_requested.emit(data_copy)

    def retranslate_ui(self):
        self.title_lbl.setText(tr("catalog.title"))
        self.filter_bar.retranslate_ui()
        self.provider_drawer.retranslate_ui()
        self.pagination_bar.retranslate_ui()
        self.pagination_bar.update_pagination(self.current_page, self.total_pages, self.total_items)
        self.refresh_catalog()
