"""
Update-related asynchronous background workers for Qt UI.
"""

from typing import Optional, List
from PySide6.QtCore import Signal

from src.api.client import get_api_client
from src.utils.logger import logger
from src.utils.thread_utils import BaseWorker


class UpdateWorker(BaseWorker):
    """Asynchronous worker for updating a single mod, a batch of selected mods, or all mods."""

    finished = Signal(bool, str)

    def __init__(
        self,
        mode: str = "single",
        installed_id: Optional[int] = None,
        installed_ids: Optional[List[int]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.mode = mode
        self.installed_id = installed_id
        self.installed_ids = installed_ids or []

    def run(self):
        """Exécute l'opération run."""
        self._is_running = True
        client = get_api_client()
        try:
            if self._is_cancelled:
                return
            if self.mode == "single" and self.installed_id:
                res = client.update_mod(self.installed_id)
            elif self.mode == "batch" and self.installed_ids:
                res = client.update_selected_mods(self.installed_ids)
            else:
                res = client.update_all_mods()

            if not self._is_cancelled:
                self.finished.emit(res.get("success", False), res.get("message", ""))
        except Exception as e:
            if not self._is_cancelled:
                logger.error(f"UpdateWorker error: {e}")
                self.finished.emit(False, f"Erreur API lors de la mise à jour: {e}")
        finally:
            self._is_running = False
