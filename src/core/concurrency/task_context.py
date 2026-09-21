"""Contexte d'exécution de tâche avec support d'annulation et suivi de progression."""

from __future__ import annotations

import threading
from typing import Any, Callable, Optional


class CancellationToken:
    """Jeton d'annulation thread-safe pour stopper proprement les tâches longues."""

    def __init__(self) -> None:
        self._is_cancelled = threading.Event()

    def cancel(self) -> None:
        """Déclenche l'annulation de la tâche."""
        self._is_cancelled.set()

    @property
    def is_cancelled(self) -> bool:
        """Indique si l'annulation a été demandée."""
        return self._is_cancelled.is_set()

    def check_cancelled(self) -> None:
        """Lève une exception InterruptedError si annulé."""
        if self.is_cancelled:
            raise InterruptedError("L'opération a été annulée par l'utilisateur ou le système.")


class TaskProgress:
    """Rapporteur de progression thread-safe."""

    def __init__(self, callback: Optional[Callable[[int, int, str], None]] = None) -> None:
        self.callback = callback
        self._lock = threading.Lock()

    def update(self, current: int, total: int, message: str = "") -> None:
        """Met à jour la progression courante."""
        if self.callback:
            with self._lock:
                try:
                    self.callback(current, total, message)
                except Exception:
                    pass


class TaskContext:
    """Contexte d'exécution unifié liant annulation, progression et métadonnées."""

    def __init__(
        self,
        token: Optional[CancellationToken] = None,
        progress: Optional[TaskProgress] = None,
        task_id: str = "",
    ) -> None:
        self.token = token or CancellationToken()
        self.progress = progress or TaskProgress()
        self.task_id = task_id
        self._metadata: dict[str, Any] = {}

    def set_meta(self, key: str, value: Any) -> None:
        """Assigne une métadonnée au contexte."""
        self._metadata[key] = value

    def get_meta(self, key: str, default: Any = None) -> Any:
        """Récupère une métadonnée du contexte."""
        return self._metadata.get(key, default)
