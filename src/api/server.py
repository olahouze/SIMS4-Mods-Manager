import time
import threading
import uvicorn
from typing import Optional
import httpx

from src.utils.logger import logger


class ApiServer:
    """Manages Uvicorn FastAPI server in standalone mode or background daemon thread."""

    _server_instance: Optional[uvicorn.Server] = None
    _server_thread: Optional[threading.Thread] = None
    _host: str = "127.0.0.1"
    _port: int = 8000

    @classmethod
    def start_background(cls, host: str = "127.0.0.1", port: int = 8000, wait_ready: bool = True) -> int:
        """
        Starts the FastAPI server in a background daemon thread.
        Waits for readiness before returning.
        """
        cls._host = host
        cls._port = port

        config = uvicorn.Config(
            app="src.api.app:app",
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
            reload=False,
        )
        cls._server_instance = uvicorn.Server(config)

        def _run():
            try:
                cls._server_instance.run()
            except Exception as e:
                logger.error(f"Erreur du serveur API en arrière-plan: {e}")

        cls._server_thread = threading.Thread(target=_run, daemon=True, name="FastApiServerThread")
        cls._server_thread.start()

        if wait_ready:
            cls.wait_until_ready(host, port, timeout=5.0)

        logger.info(f"Serveur API démarré avec succès en arrière-plan sur http://{host}:{port}")
        return port

    @classmethod
    def wait_until_ready(cls, host: str, port: int, timeout: float = 5.0) -> bool:
        """Polls the fast ping endpoint until the server is up or timeout occurs."""
        url = f"http://{host}:{port}/api/system/ping"
        deadline = time.time() + timeout
        with httpx.Client(timeout=0.5) as client:
            while time.time() < deadline:
                try:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        return True
                except Exception:
                    time.sleep(0.1)
        logger.warning(f"Le serveur API n'a pas répondu dans le délai imparti de {timeout}s.")
        return False

    @classmethod
    def run_standalone(cls, host: str = "127.0.0.1", port: int = 8000):
        """Runs the FastAPI server synchronously in foreground (standalone mode)."""
        cls._host = host
        cls._port = port
        logger.info(f"Démarrage du serveur API autonome sur http://{host}:{port}")
        logger.info(f"Documentation Swagger interactive disponible sur : http://{host}:{port}/docs")

        config = uvicorn.Config(
            app="src.api.app:app",
            host=host,
            port=port,
            log_level="info",
            access_log=True,
            reload=False,
        )
        server = uvicorn.Server(config)
        server.run()

    @classmethod
    def stop(cls):
        """Stops the running server if active."""
        if cls._server_instance:
            cls._server_instance.should_exit = True
