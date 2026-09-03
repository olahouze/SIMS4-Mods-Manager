import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

from src.core.config import AppConfig
from src.core.database import DatabaseManager
from src.core.game_detector import GameDetector
from src.core.mod_installer import ModInstaller
from src.core.session_manager import SessionManager
from src.providers import ProviderRegistry
from src.ui.app import MainWindow
from src.utils.logger import logger

def main():
    logger.info("Initializing SIMS 4 Mods Manager...")

    # 1. Initialize Configuration & Database
    config = AppConfig.load()
    db = DatabaseManager.get_instance()

    # 2. Initialize Source Providers
    ProviderRegistry.initialize()

    # 3. Detect Game & Scan existing mods
    mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
    if mods_dir:
        logger.info(f"Sims 4 Mods folder detected: {mods_dir}")
        try:
            found = ModInstaller.scan_existing_mods()
            logger.info(f"Scanned {len(found)} mod(s) in Mods directory.")
        except Exception as e:
            logger.warning(f"Initial mods scan warning: {e}")
    else:
        logger.warning("Sims 4 Mods folder could not be detected automatically.")

    # 4. Launch Qt Application
    # High-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("SIMS 4 Mods Manager")
    app.setOrganizationName("OLAHOUZE")

    # 5. Check Playwright Browser Availability
    if not SessionManager.is_browser_available():
        logger.warning("No Playwright browser engine found on system.")
        QMessageBox.warning(
            None,
            "Navigateur Requis pour l'Anti-Bot",
            "Aucun navigateur compatible (Chromium, Edge ou Chrome) n'a été détecté pour Playwright.\n\n"
            "Pour activer les connexions automatiques et le contournement Cloudflare, veuillez exécuter la commande :\n\n"
            "uv run playwright install chromium"
        )
    else:
        logger.info("Playwright browser engine verified and ready.")

    # 6. Check & Log Stored Sessions
    for p_name in ["loverslab", "patreon"]:
        acc = SessionManager.get_saved_session(p_name)
        ready = SessionManager.is_session_ready(p_name)
        if acc:
            c_count = len(acc.get_cookies_dict())
            logger.info(
                f"État session '{p_name}': {'Prête (✓)' if ready else 'Incomplète (✗)'} "
                f"({c_count} cookies enregistrés, identifiant: '{acc.user_display_name or 'Anonyme/Anti-bot validé'}')."
            )
        else:
            logger.info(f"État session '{p_name}': Non configurée.")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
