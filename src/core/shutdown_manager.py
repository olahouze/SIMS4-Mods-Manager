import threading
from typing import List, Callable


class ShutdownManager:
    """
    Thread-safe global coordinator for graceful application shutdown.
    Allows background scrapers, workers, and timers to stop scheduling new tasks
    cleanly before interpreter teardown.
    """

    _shutting_down: bool = False
    _lock = threading.Lock()
    _callbacks: List[Callable[[], None]] = []

    @classmethod
    def is_shutting_down(cls) -> bool:
        """Exécute l'opération is shutting down.

        Returns:
            Résultat de l'opération is_shutting_down.
        """
        return cls._shutting_down

    @classmethod
    def reset(cls):
        """Resets the shutdown state and callbacks list. Useful for test environments."""
        with cls._lock:
            cls._shutting_down = False
            cls._callbacks.clear()

    @classmethod
    def trigger_shutdown(cls):
        """Exécute l'opération trigger shutdown."""
        with cls._lock:
            if cls._shutting_down:
                return
            cls._shutting_down = True

        for cb in list(cls._callbacks):
            try:
                cb()
            except Exception:
                pass

    @classmethod
    def register_callback(cls, callback: Callable[[], None]):
        """Exécute l'opération register callback.

        Args:
            callback: Paramètre callback.
        """
        with cls._lock:
            if callback not in cls._callbacks:
                cls._callbacks.append(callback)

    @classmethod
    def register_shutdown_callback(cls, callback: Callable[[], None]):
        """Exécute l'opération register shutdown callback.

        Args:
            callback: Paramètre callback.
        """
        cls.register_callback(callback)
