import sys
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.logger import logger
from src.utils.network import find_available_port
from src.api.server import ApiServer
from src.api.client import init_api_client


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

    args = parser.parse_args()

    # 1. Vérification et allocation dynamique de port libre
    initial_port = args.port
    port = find_available_port(host=args.host, start_port=initial_port)

    if port != initial_port:
        logger.warning(
            f"Le port demandé {initial_port} était occupé. Basculement automatique sur le port libre {port}."
        )
    else:
        logger.info(f"Port {port} vérifié et disponible.")

    # 2. Mode Serveur Autonome (API pure, pas de GUI)
    if args.server_mode:
        logger.info(f"Mode serveur autonome activé sur http://{args.host}:{port}")
        ApiServer.run_standalone(host=args.host, port=port)
        return

    # 3. Mode Par Défaut (API en tâche de fond + GUI PySide6)
    logger.info("Démarrage de l'application en mode GUI (avec API REST en tâche de fond)...")

    # Démarrage du serveur API dans un thread daemon
    ApiServer.start_background(host=args.host, port=port, wait_ready=True)

    # Initialisation du client API global pour la GUI
    api_url = f"http://{args.host}:{port}"
    client = init_api_client(base_url=api_url)
    logger.info(f"Client API configuré sur {api_url}")

    # Initialisation de Qt
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import Qt
    from src.ui.app import MainWindow

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("SIMS 4 Mods Manager")
    app.setOrganizationName("OLAHOUZE")

    # Diagnostic de santé via l'API
    try:
        health = client.get_health()
        if not health.get("browser_engine_ready", False):
            logger.warning("Aucun moteur de navigateur détecté pour Playwright via l'API.")
            QMessageBox.warning(
                None,
                "Navigateur Requis pour l'Anti-Bot",
                "Aucun navigateur compatible (Chromium, Edge ou Chrome) n'a été détecté pour Playwright.\n\n"
                "Pour activer les connexions automatiques et le contournement Cloudflare, veuillez exécuter :\n\n"
                "uv run playwright install chromium",
            )
        else:
            logger.info("Vérification Playwright réussie via l'API.")

        # Scan initial automatique des mods via l'API
        scan_res = client.scan_installed_mods()
        logger.info(f"Scan initial terminé via l'API : {scan_res.get('message', '')}")
    except Exception as e:
        logger.error(f"Avertissement lors des vérifications initiales API: {e}")

    # Lancement de la fenêtre principale
    window = MainWindow()
    window.show()

    # Démarrage de la vérification des dossiers du jeu et des mods installés en tâche de fond
    from src.core.game_detector import GameDetector
    from src.core.mod_installer import ModInstaller

    GameDetector.start_background_detection_refresh()
    ModInstaller.start_background_installed_mods_verifier()

    exit_code = app.exec()
    ApiServer.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
