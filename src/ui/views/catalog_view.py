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
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer

from src.api.client import get_api_client
from src.ui.components.filter_bar import FilterBar
from src.ui.components.mod_card import ModCard
from src.ui.components.mod_detail_modal import ModDetailModal
from src.ui.components.progress_dialog import ProgressDialog
from src.utils.logger import logger


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
            }

            for event in client.install_mod_stream(payload):
                evt_type = event.get("type")
                if evt_type == "progress":
                    self.progress.emit(
                        event.get("percent", 0),
                        event.get("status", "Installation..."),
                        event.get("details", ""),
                    )
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.current_page = 1
        self.page_size = 24
        self.total_items = 0
        self.total_pages = 1

        self._page1_displayed = False
        self._last_pages_completed = 0

        # Background sync monitoring timer
        self.monitor_timer = QTimer(self)
        self.monitor_timer.setInterval(1200)
        self.monitor_timer.timeout.connect(self._check_sync_status)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
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

        # Initial data load
        self.refresh_catalog()

        # Check if background sync is already active on startup
        self.start_sync_monitoring()

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

    def start_sync(self, max_pages: int = 0):
        """Starts background synchronization non-blockingly and activates banner monitoring (0 = all pages)."""
        try:
            self._page1_displayed = False
            self._last_pages_completed = 0
            self.api_client.start_catalog_sync(max_pages=max_pages)
            self.start_sync_monitoring()
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Impossible de lancer la synchronisation : {e}")

    def start_sync_monitoring(self):
        """Starts timer to monitor sync status, enabling immediate page 1 rendering and banner updates."""
        try:
            status = self.api_client.get_catalog_sync_status()
            if status.get("is_running", False):
                self.sync_banner.setVisible(True)
                self.sync_banner_lbl.setText(status.get("message", "Synchronisation en cours..."))
                self.sync_bar.setValue(status.get("progress_percent", 0))
                if not self.monitor_timer.isActive():
                    self.monitor_timer.start()
        except Exception as e:
            logger.debug(f"Sync status check on startup: {e}")

    def _check_sync_status(self):
        """Polls API for background synchronization updates."""
        try:
            status = self.api_client.get_catalog_sync_status()
            is_running = status.get("is_running", False)
            pct = status.get("progress_percent", 0)
            msg = status.get("message", "Synchronisation...")
            pages_done = status.get("pages_completed", 0)
            page1_ready = status.get("page1_ready", False)

            if is_running:
                self.sync_banner.setVisible(True)
                self.sync_banner_lbl.setText(f"🔄 {msg}")
                self.sync_bar.setValue(pct)

                # 1. Immediate Page 1 Rendering: As soon as page 1 is ready, show it instantly!
                if page1_ready and not self._page1_displayed:
                    self._page1_displayed = True
                    self._last_pages_completed = pages_done
                    logger.info("Page 1 prête : rafraîchissement immédiat de la vue catalogue.")
                    self.refresh_catalog()

                # 2. Progressive Updates: As subsequent pages complete, refresh catalog
                elif pages_done > self._last_pages_completed:
                    self._last_pages_completed = pages_done
                    logger.info(f"Page(s) supplémentaire(s) traitée(s) ({pages_done}) : mise à jour du catalogue.")
                    self.refresh_catalog()

            else:
                # Sync completed
                self.monitor_timer.stop()
                self.sync_banner.setVisible(False)
                total = status.get("total_scraped", 0)
                logger.info(f"Synchronisation en tâche de fond achevée. Total indexé: {total}.")
                self.refresh_catalog()

        except Exception as e:
            logger.debug(f"Erreur lors de la vérification du statut de sync: {e}")

    def install_mod(self, mod_data: dict):
        """Starts background download and installation of selected mod via API."""
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

    def _show_mod_details(self, mod_data: dict, is_installed: bool = False):
        """Displays overlay modal taking the full space of the catalog view."""
        modal = ModDetailModal(mod_data, is_installed=is_installed, parent=self)
        if self.width() > 100 and self.height() > 100:
            modal.resize(self.size())
            modal.move(self.mapToGlobal(self.rect().topLeft()))
        modal.install_requested.connect(self.install_mod)
        modal.exec()
