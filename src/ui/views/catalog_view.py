import math
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QLabel,
    QMessageBox,
    QDialog,
)
from PySide6.QtCore import Signal, QTimer

from src.api.client import get_api_client
from src.ui.components.filter_bar import FilterBar
from src.ui.components.mod_card import ModCard
from src.ui.components.responsive_card_grid import ResponsiveCardGrid
from src.ui.components.dependencies_dialog import DependenciesDialog
from src.ui.components.progress_dialog import ProgressDialog
from src.ui.components.provider_drawer import ProviderDrawer
from src.ui.workers.catalog_workers import SyncTriggerWorker, InstallWorker, CatalogFetchWorker
from src.ui.views.catalog.filter_adapter import build_catalog_api_params
from src.ui.views.catalog.catalog_widgets import CatalogSyncBannerWidget, CatalogPaginationBar
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
            elif has_error:
                if self.monitor_timer.interval() != self.IDLE_MONITOR_INTERVAL_MS:
                    self.monitor_timer.setInterval(self.IDLE_MONITOR_INTERVAL_MS)
                self.sync_banner_widget.set_error(err_msg or msg)
            else:
                if self.monitor_timer.interval() != self.IDLE_MONITOR_INTERVAL_MS:
                    self.monitor_timer.setInterval(self.IDLE_MONITOR_INTERVAL_MS)
                self.sync_banner_widget.set_idle()
                if self._last_pages_completed > 0:
                    self._last_pages_completed = 0
                    self.refresh_catalog()

        except Exception as e:
            logger.debug(f"Erreur vérification statut sync: {e}")

    def install_mod(self, mod_data: dict):
        mod_id = mod_data.get("id")
        try:
            dep_res = self.api_client.check_dependencies(mod_id)
            if dep_res and (dep_res.get("missing") or dep_res.get("already_installed") or dep_res.get("game_dlcs")):
                dlg = DependenciesDialog(
                    mod_title=dep_res.get("mod_title", mod_data.get("title", "")),
                    already_installed=dep_res.get("already_installed", []),
                    missing=dep_res.get("missing", []),
                    unfound=dep_res.get("unfound", []),
                    is_partial=dep_res.get("is_partial", False),
                    game_dlcs=dep_res.get("game_dlcs", []),
                    mod_data=mod_data,
                    parent=self,
                )
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return
        except Exception as e:
            logger.warning(f"Impossible de vérifier les dépendances avant installation: {e}")

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
        data_copy = dict(mod_data)
        data_copy["is_installed"] = is_installed
        self.details_requested.emit(data_copy)

    def retranslate_ui(self):
        self.title_lbl.setText(tr("catalog.title"))
        self.filter_bar.retranslate_ui()
        self.provider_drawer.retranslate_ui()
        self.pagination_bar.update_pagination(self.current_page, self.total_pages, self.total_items)
        self.refresh_catalog()
