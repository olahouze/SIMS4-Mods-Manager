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
from src.ui.theme import DARK_THEME_QSS
from src.ui.views.catalog_view import CatalogView
from src.ui.views.installed_view import InstalledView
from src.ui.views.updates_view import UpdatesView
from src.ui.views.accounts_view import AccountsView
from src.ui.views.settings_view import SettingsView
from src.ui.views.logs_view import LogsView


class MainWindow(QMainWindow):
    """Main application window for SIMS 4 Mods Manager connected 100% via REST API."""

    def __init__(self):
        super().__init__()
        self.api_client = get_api_client()
        self.setWindowTitle("SIMS 4 Mods Manager")
        self.resize(1280, 800)
        self.setMinimumSize(1000, 650)
        self.setStyleSheet(DARK_THEME_QSS)

        self.init_ui()
        self.refresh_game_status()
        self.update_nav_badge()

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

        self.btn_accounts = self._create_nav_button("🌐  Comptes & Anti-Bot", 0)
        self.btn_catalog = self._create_nav_button("📁  Catalogue Unifié", 1)
        self.btn_installed = self._create_nav_button("💾  Mes Mods", 2)
        self.btn_updates = self._create_nav_button("🔄  Mises à Jour", 3)
        self.btn_logs = self._create_nav_button("📋  Journaux & Logs", 4)
        self.btn_settings = self._create_nav_button("⚙️  Paramètres", 5)

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

        self.game_status = QLabel("Vérification du jeu...")
        self.game_status.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 600; padding: 4px 0;")
        footer_layout.addWidget(self.game_status)

        play_btn = QPushButton("▶ Lancer Les Sims 4")
        play_btn.setStyleSheet("""
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
        play_btn.clicked.connect(self._launch_game)
        footer_layout.addWidget(play_btn)

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

        self.stacked_widget.addWidget(self.accounts_view)  # Index 0 (Comptes)
        self.stacked_widget.addWidget(self.catalog_view)  # Index 1 (Catalogue)
        self.stacked_widget.addWidget(self.installed_view)  # Index 2 (Installés)
        self.stacked_widget.addWidget(self.updates_view)  # Index 3 (Mises à jour)
        self.stacked_widget.addWidget(self.logs_view)  # Index 4 (Logs)
        self.stacked_widget.addWidget(self.settings_view)  # Index 5 (Paramètres)

        content_layout.addWidget(self.stacked_widget)
        main_layout.addWidget(content_area)

        # Connect login signal to switch to catalog
        self.accounts_view.login_successful.connect(self._on_login_success)

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

    def _on_login_success(self, provider_name: str):
        """Switches to catalog and triggers progressive loading monitoring."""
        self.switch_page(1)
        if hasattr(self.catalog_view, "start_sync_monitoring"):
            self.catalog_view.start_sync_monitoring()

    def refresh_game_status(self):
        """Checks game status through API /api/system/health."""
        try:
            health = self.api_client.get_health()
            mods_detected = health.get("mods_dir_detected", False)
            if mods_detected:
                self.game_status.setText("✓ Jeu & Mods Détectés")
                self.game_status.setStyleSheet("font-size: 11px; color: #34d399; font-weight: 600; padding: 4px 0;")
            else:
                self.game_status.setText("⚠️ Dossier Mods Non Détecté")
                self.game_status.setStyleSheet("font-size: 11px; color: #f87171; font-weight: 600; padding: 4px 0;")
        except Exception:
            self.game_status.setText("⚠️ Erreur statut API")
            self.game_status.setStyleSheet("font-size: 11px; color: #f87171; font-weight: 600; padding: 4px 0;")

    def update_nav_badge(self):
        """Updates the badge on updates nav button using API /api/updates."""
        try:
            data = self.api_client.get_updates()
            count = data.get("count", 0)
            if count > 0:
                self.btn_updates.setText(f"🔄  Mises à Jour ({count})")
            else:
                self.btn_updates.setText("🔄  Mises à Jour")
        except Exception:
            self.btn_updates.setText("🔄  Mises à Jour")

    def _launch_game(self):
        """Launches The Sims 4 via API /api/game/launch."""
        try:
            res = self.api_client.launch_game()
            QMessageBox.information(self, "Lancement du jeu", res.get("message", "Jeu lancé."))
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Échec du lancement du jeu: {e}")
