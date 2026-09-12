from PySide6.QtCore import QTimer, QObject, Signal, QRunnable, QThreadPool
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QStackedWidget,
    QPushButton,
    QLabel,
    QFrame,
    QMessageBox,
)

from src.api.client import get_api_client
from src.core.config import AppConfig
from src.core.shutdown_manager import ShutdownManager
from src.i18n import I18nManager, tr
from src.ui.theme import DARK_THEME_QSS
from src.ui.views.accounts_view import AccountsView
from src.ui.views.catalog_view import CatalogView
from src.ui.views.installed_view import InstalledView
from src.ui.views.logs_view import LogsView
from src.ui.views.mod_detail_view import ModDetailView
from src.ui.views.settings_view import SettingsView
from src.ui.views.updates_view import UpdatesView
from src.utils.logger import logger


class StatusCheckSignals(QObject):
    health_checked = Signal(bool, bool)  # success, mods_detected
    updates_checked = Signal(int)  # updates_count


class BackgroundStatusWorker(QRunnable):
    """Executes lightweight health and updates checks off the Qt GUI thread."""

    def __init__(self, api_client, signals: StatusCheckSignals):
        super().__init__()
        self.api_client = api_client
        self.signals = signals

    def run(self):
        try:
            health = self.api_client.get_health()
            self.signals.health_checked.emit(True, health.get("mods_dir_detected", False))
        except Exception:
            self.signals.health_checked.emit(False, False)

        try:
            data = self.api_client.get_updates()
            self.signals.updates_checked.emit(data.get("count", 0))
        except Exception:
            self.signals.updates_checked.emit(0)


class MainWindow(QMainWindow):
    """Main application window for SIMS 4 Mods Manager connected 100% via REST API."""

    def __init__(self):
        super().__init__()
        self.api_client = get_api_client()
        self.i18n = I18nManager.instance()
        self.status_signals = StatusCheckSignals()
        self.status_signals.health_checked.connect(self._on_health_checked)
        self.status_signals.updates_checked.connect(self._on_updates_checked)

        # Initialize language from saved configuration
        initial_lang = AppConfig.load().language
        self.i18n.set_language(initial_lang)

        self.setWindowTitle(tr("app.window_title"))
        self.resize(1280, 800)
        self.setMinimumSize(1000, 650)
        self.setStyleSheet(DARK_THEME_QSS)

        self.init_ui()
        self.i18n.language_changed.connect(self.retranslate_ui)
        self.refresh_game_status()
        self.update_nav_badge()

        # Automatically check and trigger background sync once connection/API is ready
        QTimer.singleShot(1500, self.auto_start_background_sync)

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Left Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 20)
        sidebar_layout.setSpacing(8)

        # Brand / Logo Header
        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(2)

        app_title = QLabel("SIMS 4")
        app_title.setObjectName("AppTitle")
        brand_layout.addWidget(app_title)

        app_subtitle = QLabel("MODS MANAGER")
        app_subtitle.setObjectName("AppSubtitle")
        brand_layout.addWidget(app_subtitle)

        sidebar_layout.addLayout(brand_layout)
        sidebar_layout.addSpacing(20)

        # Navigation Buttons
        self.nav_buttons = []

        self.btn_accounts = self._create_nav_button(tr("nav.accounts"), 0)
        self.btn_catalog = self._create_nav_button(tr("nav.catalog"), 1)
        self.btn_installed = self._create_nav_button(tr("nav.installed"), 2)
        self.btn_updates = self._create_nav_button(tr("nav.updates"), 3)
        self.btn_logs = self._create_nav_button(tr("nav.logs"), 4)
        self.btn_settings = self._create_nav_button(tr("nav.settings"), 5)

        sidebar_layout.addWidget(self.btn_accounts)
        sidebar_layout.addWidget(self.btn_catalog)
        sidebar_layout.addWidget(self.btn_installed)
        sidebar_layout.addWidget(self.btn_updates)
        sidebar_layout.addWidget(self.btn_logs)
        sidebar_layout.addWidget(self.btn_settings)

        sidebar_layout.addStretch()

        # Quick Launch Game in Sidebar Footer
        footer_layout = QVBoxLayout()
        footer_layout.setSpacing(6)

        self.game_status = QLabel(tr("nav.game_checking"))
        self.game_status.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 600; padding: 4px 0;")
        footer_layout.addWidget(self.game_status)

        self.play_btn = QPushButton(tr("nav.launch_game"))
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                border-radius: 8px;
                padding: 10px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.play_btn.clicked.connect(self._launch_game)
        footer_layout.addWidget(self.play_btn)

        sidebar_layout.addLayout(footer_layout)
        main_layout.addWidget(sidebar)

        # 2. Right Content Stacked Pages
        content_area = QFrame()
        content_area.setObjectName("ContentArea")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget = QStackedWidget()

        # Views
        self.accounts_view = AccountsView()
        self.catalog_view = CatalogView()
        self.installed_view = InstalledView()
        self.updates_view = UpdatesView()
        self.logs_view = LogsView()
        self.settings_view = SettingsView()
        self.mod_detail_view = ModDetailView()

        self.stacked_widget.addWidget(self.accounts_view)  # Index 0 (Comptes)
        self.stacked_widget.addWidget(self.catalog_view)  # Index 1 (Catalogue)
        self.stacked_widget.addWidget(self.installed_view)  # Index 2 (Installés)
        self.stacked_widget.addWidget(self.updates_view)  # Index 3 (Mises à jour)
        self.stacked_widget.addWidget(self.logs_view)  # Index 4 (Logs)
        self.stacked_widget.addWidget(self.settings_view)  # Index 5 (Paramètres)
        self.stacked_widget.addWidget(self.mod_detail_view)  # Index 6 (Détails Plein Écran)

        content_layout.addWidget(self.stacked_widget)
        main_layout.addWidget(content_area)

        # Connect login signal to switch to catalog
        self.accounts_view.login_successful.connect(self._on_login_success)

        # Connect detail view signals for full-page mod view (from Catalog and from Installed)
        self.catalog_view.details_requested.connect(
            lambda d: self.show_mod_details(d, origin_name="Catalogue", origin_index=1)
        )
        self.installed_view.details_requested.connect(
            lambda d: self.show_mod_details(d, origin_name="Mes Mods", origin_index=2)
        )
        self.mod_detail_view.back_requested.connect(self._on_detail_back)
        self.mod_detail_view.install_requested.connect(self._on_detail_install_requested)
        self.mod_detail_view.open_folder_requested.connect(self.installed_view.open_mod_folder)

        # Cross-view synchronization when mods are installed, uninstalled, or updated
        self.catalog_view.install_finished.connect(self._on_mods_state_changed)
        self.installed_view.mods_changed.connect(self._on_mods_state_changed)
        self.updates_view.updates_applied.connect(self._on_mods_state_changed)

        # Store navigation history for back button
        self.current_origin_index = 1

        # Set default page to Accounts (Index 0)
        self.switch_page(0)

    def _create_nav_button(self, text: str, page_index: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("class", "NavButton")
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self.switch_page(page_index))
        self.nav_buttons.append(btn)
        return btn

    def switch_page(self, index: int):
        self.stacked_widget.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

        # Refresh page contents via API when switched
        if index == 0:
            self.accounts_view.refresh_statuses()
        elif index == 1:
            self.catalog_view.refresh_catalog()
        elif index == 2:
            self.installed_view.refresh_mods()
        elif index == 3:
            self.updates_view.refresh_updates()
        elif index == 4:
            self.logs_view.load_initial_history()
        elif index == 5:
            self.settings_view.load_settings()

        self.refresh_game_status()
        self.update_nav_badge()

    def show_mod_details(self, mod_data: dict, origin_name: str = "Catalogue", origin_index: int = 1):
        """Displays full-screen dedicated ModDetailView taking 100% of application area."""
        self.current_origin_index = origin_index
        for btn in self.nav_buttons:
            btn.setChecked(False)
        self.stacked_widget.setCurrentIndex(6)
        self.mod_detail_view.load_mod(mod_data, origin_name=origin_name, origin_index=origin_index)

    def _on_detail_back(self):
        """Returns to previous view (Catalog or Installed Mods)."""
        self.switch_page(self.current_origin_index)

    def _on_detail_install_requested(self, mod_data: dict):
        """
        Installs mod from ModDetailView by delegating directly to CatalogView.
        CatalogView handles single dependency verification and confirmation dialog.
        """
        self.catalog_view.install_mod(mod_data)

    def _on_mods_state_changed(self, *args):
        """Refreshes all views and navigation badges whenever mods are added, removed, or updated."""
        self.installed_view.refresh_mods()
        self.updates_view.refresh_updates()
        self.catalog_view.refresh_catalog()
        self.update_nav_badge()
        if self.stacked_widget.currentIndex() == 6:
            self._refresh_current_mod_detail()

    def _refresh_current_mod_detail(self):
        """Updates current mod in ModDetailView to reflect its new installation status."""
        try:
            curr_mod = getattr(self.mod_detail_view, "mod_data", None)
            if not curr_mod:
                return
            installed_res = self.api_client.get_installed_mods()
            installed_list = installed_res.get("items", []) if isinstance(installed_res, dict) else []
            r_id = str(curr_mod.get("remote_id", ""))
            m_title = curr_mod.get("title", "")
            match = next(
                (
                    im
                    for im in installed_list
                    if (r_id and str(im.get("remote_id", "")) == r_id) or (m_title and im.get("title") == m_title)
                ),
                None,
            )
            updated_data = dict(curr_mod)
            updated_data["is_installed"] = bool(match)
            if match:
                updated_data["folder_name"] = match.get("folder_name")
            else:
                updated_data.pop("folder_name", None)
            self.mod_detail_view.load_mod(
                updated_data,
                origin_name=self.mod_detail_view.origin_name,
                origin_index=self.mod_detail_view.origin_index,
            )
        except Exception as e:
            logger.debug(f"Erreur actualisation mod_detail_view: {e}")

    def _on_login_success(self, provider_name: str):
        """Switches to catalog and triggers progressive loading monitoring."""
        self.switch_page(1)
        if hasattr(self.catalog_view, "start_sync_monitoring"):
            self.catalog_view.start_sync_monitoring()

    def retranslate_ui(self):
        """Retranslates all navigation elements, titles and propagates to child views."""
        self.setWindowTitle(tr("app.window_title"))
        self.btn_accounts.setText(tr("nav.accounts"))
        self.btn_catalog.setText(tr("nav.catalog"))
        self.btn_installed.setText(tr("nav.installed"))
        self.btn_logs.setText(tr("nav.logs"))
        self.btn_settings.setText(tr("nav.settings"))
        self.play_btn.setText(tr("nav.launch_game"))
        self.refresh_game_status()
        self.update_nav_badge()

        # Propagate to sub-views if they implement retranslate_ui
        for view in [
            self.accounts_view,
            self.catalog_view,
            self.installed_view,
            self.updates_view,
            self.logs_view,
            self.settings_view,
            self.mod_detail_view,
        ]:
            if hasattr(view, "retranslate_ui") and callable(view.retranslate_ui):
                try:
                    view.retranslate_ui()
                except Exception as e:
                    logger.debug(f"Erreur retranslate_ui sur {type(view).__name__}: {e}")

    def refresh_game_status(self):
        """Asynchronously checks game status and updates through background worker."""
        worker = BackgroundStatusWorker(self.api_client, self.status_signals)
        QThreadPool.globalInstance().start(worker)

    def _on_health_checked(self, success: bool, mods_detected: bool):
        """Callback received on Qt GUI thread when health check completes."""
        if success:
            if mods_detected:
                self.game_status.setText(tr("nav.game_detected"))
                self.game_status.setStyleSheet("font-size: 11px; color: #34d399; font-weight: 600; padding: 4px 0;")
            else:
                self.game_status.setText(tr("nav.game_not_detected"))
                self.game_status.setStyleSheet("font-size: 11px; color: #f87171; font-weight: 600; padding: 4px 0;")
        else:
            self.game_status.setText(tr("nav.game_api_error"))
            self.game_status.setStyleSheet("font-size: 11px; color: #f87171; font-weight: 600; padding: 4px 0;")

    def update_nav_badge(self):
        """Triggers asynchronous update count check."""
        # The BackgroundStatusWorker checks both health and updates in a single light task
        self.refresh_game_status()

    def _on_updates_checked(self, count: int):
        """Callback received on Qt GUI thread when updates check completes."""
        if count > 0:
            self.btn_updates.setText(tr("nav.updates_with_count", count=count))
        else:
            self.btn_updates.setText(tr("nav.updates"))

    def _launch_game(self):
        """Launches The Sims 4 via API /api/game/launch."""
        try:
            res = self.api_client.launch_game()
            QMessageBox.information(
                self, tr("nav.launch_game_title"), res.get("message", tr("nav.launch_game_success"))
            )
        except Exception as e:
            QMessageBox.warning(
                self, tr("dialogs.error_title"), tr("nav.launch_game_error", error=str(e))
            )

    def auto_start_background_sync(self):
        """
        Automatically launches background catalog synchronization if the connection is OK.
        Checks if an active session or reachable provider exists, and starts sync without blocking.
        """
        try:
            # 1. Check if sync is already running
            status = self.api_client.get_catalog_sync_status()
            if status.get("is_running", False):
                if hasattr(self.catalog_view, "start_sync_monitoring"):
                    self.catalog_view.start_sync_monitoring()
                return

            # 2. Check accounts connection status
            acc_data = self.api_client.get_accounts()
            accounts = acc_data if isinstance(acc_data, list) else acc_data.get("accounts", [])
            is_connection_ok = False
            for acc in accounts:
                if acc.get("is_ready", False) or acc.get("is_member", False):
                    is_connection_ok = True
                    break

            # 3. If no saved session, check network connectivity to LoversLab
            if not is_connection_ok:
                try:
                    test_res = self.api_client.test_account("loverslab")
                    if test_res.get("success", False):
                        is_connection_ok = True
                except Exception:
                    pass

            if is_connection_ok:
                self.api_client.start_catalog_sync(max_pages=0)
                if hasattr(self.catalog_view, "start_sync_monitoring"):
                    self.catalog_view.start_sync_monitoring()
                logger.info(
                    "Synchronisation automatique intégrale en tâche de fond démarrée au lancement (connexion OK)."
                )
            else:
                logger.info("Synchronisation automatique en attente : session ou connexion non validée.")
        except Exception as e:
            logger.debug(f"Vérification automatique de synchronisation au démarrage: {e}")

    def closeEvent(self, event):
        """Clean and graceful shutdown handling."""
        logger.info("Fermeture de l'application demandée par l'utilisateur...")
        ShutdownManager.trigger_shutdown()
        if hasattr(self, "catalog_view") and hasattr(self.catalog_view, "monitor_timer"):
            try:
                self.catalog_view.monitor_timer.stop()
            except Exception:
                pass
        super().closeEvent(event)

