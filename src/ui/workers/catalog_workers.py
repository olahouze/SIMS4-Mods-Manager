"""
Workers d'arrière-plan (BaseWorker / QThreadPool) pour les opérations du catalogue :
- Déclenchement de la synchronisation (SyncTriggerWorker)
- Récupération asynchrone du catalogue (CatalogFetchWorker)
- Streaming de l'installation de mods (InstallWorker)
"""

from PySide6.QtCore import Signal

from src.api.client import get_api_client
from src.utils.logger import logger
from src.utils.thread_utils import BaseWorker


class SyncTriggerWorker(BaseWorker):
    finished_signal = Signal(bool, str)

    def __init__(self, api_client, max_pages: int = 0):
        super().__init__()
        self.api_client = api_client
        self.max_pages = max_pages

    def run(self):
        try:
            self._is_running = True
            if self._is_cancelled:
                return
            self.api_client.start_catalog_sync(max_pages=self.max_pages)
            if not self._is_cancelled:
                self.finished_signal.emit(True, "OK")
        except Exception as e:
            if not self._is_cancelled:
                self.finished_signal.emit(False, str(e))
        finally:
            self._is_running = False


class CatalogFetchWorker(BaseWorker):
    """Fetches catalog page and accounts asynchronously to keep the UI thread 100% fluid."""

    data_ready = Signal(dict, list, int)  # res, accounts, fetch_id
    error_signal = Signal(str, int)

    def __init__(self, api_client, params: dict, fetch_id: int = 0):
        super().__init__()
        self.api_client = api_client
        self.params = params
        self.fetch_id = fetch_id

    def run(self):
        try:
            self._is_running = True
            if self._is_cancelled:
                return
            accounts = self.api_client.get_accounts()
            if self._is_cancelled:
                return
            res = self.api_client.get_catalog(**self.params)
            if not self._is_cancelled:
                self.data_ready.emit(res, accounts, self.fetch_id)
        except Exception as e:
            if not self._is_cancelled:
                logger.error(f"CatalogFetchWorker error: {e}")
                self.error_signal.emit(str(e), self.fetch_id)
        finally:
            self._is_running = False


class InstallWorker(BaseWorker):
    progress = Signal(int, str, str)  # percent, status, details
    finished = Signal(bool, str)

    def __init__(self, mod_data: dict):
        super().__init__()
        self.mod_data = mod_data

    def run(self):
        client = get_api_client()
        try:
            self._is_running = True
            self.progress.emit(2, "Initialisation de l'installation...", "Préparation de la requête...")
            u_date = self.mod_data.get("updated_date")
            u_date_str = None
            if u_date:
                if hasattr(u_date, "isoformat"):
                    u_date_str = u_date.isoformat()
                elif isinstance(u_date, str) and u_date.strip():
                    u_date_str = u_date.strip()

            payload = {
                "catalog_mod_id": self.mod_data.get("id"),
                "source": self.mod_data.get("source"),
                "remote_id": self.mod_data.get("remote_id"),
                "page_url": self.mod_data.get("page_url"),
                "title": self.mod_data.get("title"),
                "updated_date": u_date_str,
                "install_dependencies": True,
            }

            for event in client.install_mod_stream(payload):
                if self._is_cancelled:
                    return
                evt_type = event.get("type")
                if evt_type == "progress":
                    pct = event.get("percent", 0)
                    st = event.get("status", "Installation...")
                    det = event.get("details", "")
                    logger.info(f"[INSTALL-PROGRESS] [{pct}%] {st} {f'({det})' if det else ''}")
                    self.progress.emit(pct, st, det)
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
            if not self._is_cancelled:
                logger.error(
                    f"Erreur API lors de l'installation du mod '{self.mod_data.get('title')}': {e}", exc_info=True
                )
                self.finished.emit(False, f"Erreur API lors de l'installation: {e}")
        finally:
            self._is_running = False
