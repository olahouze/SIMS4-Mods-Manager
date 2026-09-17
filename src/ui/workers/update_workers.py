"""
Update-related asynchronous background worker threads for Qt UI.
"""
from typing import Optional, List
from PySide6.QtCore import QThread, Signal

from src.api.client import get_api_client
from src.utils.logger import logger


class UpdateWorker(QThread):
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
        # Connect deleteLater to automatically clean up C++ Qt handles upon completion
        self.finished.connect(self.deleteLater)

    def run(self):
        client = get_api_client()
        try:
            if self.mode == "single" and self.installed_id:
                res = client.update_mod(self.installed_id)
            elif self.mode == "batch" and self.installed_ids:
                res = client.update_selected_mods(self.installed_ids)
            else:
                res = client.update_all_mods()
            self.finished.emit(res.get("success", False), res.get("message", ""))
        except Exception as e:
            logger.error(f"UpdateWorker error: {e}")
            self.finished.emit(False, f"Erreur API lors de la mise à jour: {e}")
