from PySide6.QtCore import QTimer, QObject, Signal, QRunnable, QThreadPool
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QStackedWidget,
    QFrame,
    QMessageBox,
)

from src.api.client import get_api_client
from src.core.config import AppConfig
from src.core.shutdown_manager import ShutdownManager
from src.i18n import I18nManager, tr
from src.ui.theme import DARK_THEME_QSS
from src.ui.components.sidebar_nav import SidebarNavWidget
from src.ui.views.accounts_view import AccountsView
from src.ui.views.catalog_view import CatalogView
from src.ui.views.installed_view import InstalledView
from src.ui.views.logs_view import LogsView
from src.ui.views.mod_detail_view import ModDetailView
from src.ui.views.settings_view import SettingsView
from src.ui.views.updates_view import UpdatesView
from src.utils.logger import logger
from src.utils.thread_utils import cleanup_all_threads


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

        QTimer.singleShot(1500, self.auto_start_background_sync)

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Left Sidebar
        self.sidebar = SidebarNavWidget(self)
        self.sidebar.page_requested.connect(self.switch_page)
        self.sidebar.launch_game_requested.connect(self._launch_game)
        main_layout.addWidget(self.sidebar)

        # 2. Right Content Stacked Pages
        content_area = QFrame()
        content_area.setObjectName("ContentArea")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget = QStackedWidget()

        self.accounts_view = AccountsView()
        self.catalog_view = CatalogView()
        self.installed_view = InstalledView()
        self.updates_view = UpdatesView()
        self.logs_view = LogsView()
        self.settings_view = SettingsView()
        self.mod_detail_view = ModDetailView()

        self.stacked_widget.addWidget(self.accounts_view)  # Index 0
        self.stacked_widget.addWidget(self.catalog_view)  # Index 1
        self.stacked_widget.addWidget(self.installed_view)  # Index 2
        self.stacked_widget.addWidget(self.updates_view)  # Index 3
        self.stacked_widget.addWidget(self.logs_view)  # Index 4
        self.stacked_widget.addWidget(self.settings_view)  # Index 5
        self.stacked_widget.addWidget(self.mod_detail_view)  # Index 6

        content_layout.addWidget(self.stacked_widget)
        main_layout.addWidget(content_area)

        self.accounts_view.login_successful.connect(self._on_login_success)
        self.catalog_view.details_requested.connect(
            lambda d: self.show_mod_details(d, origin_name="Catalogue", origin_index=1)
        )
        self.installed_view.details_requested.connect(
            lambda d: self.show_mod_details(d, origin_name="Mes Mods", origin_index=2)
        )
        self.mod_detail_view.back_requested.connect(self._on_detail_back)
        self.mod_detail_view.install_requested.connect(self._on_detail_install_requested)
        self.mod_detail_view.open_folder_requested.connect(self.installed_view.open_mod_folder)

        self.catalog_view.install_finished.connect(self._on_mods_state_changed)
        self.installed_view.mods_changed.connect(self._on_mods_state_changed)
        self.updates_view.updates_applied.connect(self._on_mods_state_changed)

        self.current_origin_index = 1
        self.switch_page(0)

    # Backward compatible sidebar property accessors
    @property
    def nav_buttons(self):
        return self.sidebar.nav_buttons

    @property
    def btn_accounts(self):
        return self.sidebar.btn_accounts

    @property
    def btn_catalog(self):
        return self.sidebar.btn_catalog

    @property
    def btn_installed(self):
        return self.sidebar.btn_installed

    @property
    def btn_updates(self):
        return self.sidebar.btn_updates

    @property
    def btn_logs(self):
        return self.sidebar.btn_logs

    @property
    def btn_settings(self):
        return self.sidebar.btn_settings

    @property
    def game_status(self):
        return self.sidebar.game_status

    @property
    def play_btn(self):
        return self.sidebar.play_btn

    def switch_page(self, index: int):
        self.stacked_widget.setCurrentIndex(index)
        self.sidebar.set_active_page(index)

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
        self.current_origin_index = origin_index
        for btn in self.nav_buttons:
            btn.setChecked(False)
        self.stacked_widget.setCurrentIndex(6)
        self.mod_detail_view.load_mod(mod_data, origin_name=origin_name, origin_index=origin_index)

    def _on_detail_back(self):
        self.switch_page(self.current_origin_index)

    def _on_detail_install_requested(self, mod_data: dict):
        self.catalog_view.install_mod(mod_data)

    def _on_mods_state_changed(self, *args):
        self.installed_view.refresh_mods()
        self.updates_view.refresh_updates()
        self.catalog_view.refresh_catalog()
        self.update_nav_badge()
        if self.stacked_widget.currentIndex() == 6:
            self._refresh_current_mod_detail()

    def _refresh_current_mod_detail(self):
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
        self.switch_page(1)
        if hasattr(self.catalog_view, "start_sync_monitoring"):
            self.catalog_view.start_sync_monitoring()

    def retranslate_ui(self):
        self.setWindowTitle(tr("app.window_title"))
        self.sidebar.retranslate_ui()
        self.refresh_game_status()
        self.update_nav_badge()

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

        if hasattr(self.catalog_view, "provider_drawer") and hasattr(self.catalog_view.provider_drawer, "retranslate_ui"):
            try:
                self.catalog_view.provider_drawer.retranslate_ui()
            except Exception as e:
                logger.debug(f"Erreur retranslate_ui sur provider_drawer: {e}")

    def refresh_game_status(self):
        worker = BackgroundStatusWorker(self.api_client, self.status_signals)
        QThreadPool.globalInstance().start(worker)

    def _on_health_checked(self, success: bool, mods_detected: bool):
        self.sidebar.update_game_status(success, mods_detected)

    def update_nav_badge(self):
        self.refresh_game_status()

    def _on_updates_checked(self, count: int):
        self.sidebar.update_badge_count(count)

    def _launch_game(self):
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
        try:
            status = self.api_client.get_catalog_sync_status()
            if status.get("is_running", False):
                if hasattr(self.catalog_view, "start_sync_monitoring"):
                    self.catalog_view.start_sync_monitoring()
                return

            acc_data = self.api_client.get_accounts()
            accounts = acc_data if isinstance(acc_data, list) else acc_data.get("accounts", [])
            is_connection_ok = False
            for acc in accounts:
                if acc.get("is_ready", False) or acc.get("is_member", False):
                    is_connection_ok = True
                    break

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
        logger.info("Fermeture de l'application demandée par l'utilisateur...")
        ShutdownManager.trigger_shutdown()
        if hasattr(self, "catalog_view") and hasattr(self.catalog_view, "monitor_timer"):
            try:
                self.catalog_view.monitor_timer.stop()
            except Exception:
                pass
        cleanup_all_threads(500)
        super().closeEvent(event)
