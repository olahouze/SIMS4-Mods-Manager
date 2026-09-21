import sys
import argparse
import atexit
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.logger import logger
from src.utils.network import find_available_port
from src.api.server import ApiServer
from src.api.client import init_api_client
from src.core.shutdown_manager import ShutdownManager


def main():
    parser = argparse.ArgumentParser(
        description="SIMS 4 Mods Manager - Gestionnaire de mods avec interface GUI et API REST intégrée"
    )
    parser.add_argument(
        "--server",
        "--api",
        "--headless",
        dest="server_mode",
        action="store_true",
        help="Lancer l'application en mode serveur autonome (API REST uniquement, sans GUI)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port réseau d'écoute pour l'API REST (défaut : 8000). Si occupé, un port libre sera choisi automatiquement.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Adresse IP / hôte d'écoute (défaut : 127.0.0.1)",
    )
    parser.add_argument(
        "--disable-auth",
        action="store_true",
        help="Désactive l'authentification par jeton interne (réservé aux tests et simulations)",
    )

    args = parser.parse_args()

    # Initialisation de la sécurité API locale
    from src.core.security import init_security

    token = init_security(disable_auth=args.disable_auth)

    # 1. Vérification et allocation dynamique de port libre
    initial_port = args.port
    port = find_available_port(host=args.host, start_port=initial_port)

    if port != initial_port:
        logger.warning(
            f"Le port demandé {initial_port} était occupé. Basculement automatique sur le port libre {port}."
        )
    else:
        logger.info(f"Port {port} vérifié et disponible.")

    atexit.register(ShutdownManager.trigger_shutdown)

    # 2. Mode Serveur Autonome (API pure, pas de GUI)
    if args.server_mode:
        logger.info(f"Mode serveur autonome activé sur http://{args.host}:{port}")
        try:
            ApiServer.run_standalone(host=args.host, port=port)
        finally:
            ShutdownManager.trigger_shutdown()
        return

    # 3. Mode Par Défaut (API en tâche de fond + GUI PySide6)
    logger.info("Démarrage de l'application en mode GUI (avec API REST en tâche de fond)...")

    # Démarrage non-bloquant du serveur API dans un thread daemon (tourne en parallèle du chargement Qt)
    ApiServer.start_background(host=args.host, port=port, wait_ready=False)

    # Initialisation du client API global pour la GUI
    api_url = f"http://{args.host}:{port}"
    client = init_api_client(base_url=api_url, token=token)
    logger.info(f"Client API configuré sur {api_url}")

    # Initialisation de Qt (se déroule pendant le démarrage Uvicorn)
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import Qt, QTimer
    from src.ui.app import MainWindow
    from src.utils.logger import attach_qt_handler

    from src.i18n import tr

    # Attach Qt log handler before QApplication so UI logs stream in real-time
    attach_qt_handler()

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("SIMS 4 Mods Manager")
    app.setOrganizationName("OLAHOUZE")

    # Attente express de la disponibilité de l'API (démarrée en parallèle pendant les imports Qt)
    ApiServer.wait_until_ready(args.host, port, timeout=5.0)

    # Lancement immédiat de la fenêtre principale
    window = MainWindow()
    window.show()

    # Diagnostic Playwright et scan initial exécutés en tâche différée sans bloquer l'affichage
    def _async_startup_tasks():
        try:
            health = client.get_health()
            if not health.get("browser_engine_ready", False):
                logger.warning("Aucun moteur de navigateur détecté pour Playwright via l'API.")
                QMessageBox.warning(
                    window,
                    tr("app.browser_required_title"),
                    tr("app.browser_required_msg"),
                )
            else:
                logger.info("Vérification Playwright réussie via l'API.")

            # Scan initial des mods sans geler l'interface graphique
            scan_res = client.scan_installed_mods()
            logger.info(f"Scan initial terminé via l'API : {scan_res.get('message', '')}")
            if hasattr(window, "installed_view"):
                window.installed_view.refresh_mods()
            if hasattr(window, "update_nav_badge"):
                window.update_nav_badge()
        except Exception as e:
            logger.error(f"Avertissement lors des vérifications initiales API: {e}")

    QTimer.singleShot(50, _async_startup_tasks)

    # Démarrage de la vérification des dossiers du jeu et des mods installés en tâche de fond
    from src.application.game.game_service import GameDetector
    from src.application.mods.mod_installer_service import ModInstaller

    GameDetector.start_background_detection_refresh()
    ModInstaller.start_background_installed_mods_verifier()

    exit_code = app.exec()
    ShutdownManager.trigger_shutdown()
    ApiServer.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
