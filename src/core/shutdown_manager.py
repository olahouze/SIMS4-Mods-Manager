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
        return cls._shutting_down

    @classmethod
    def trigger_shutdown(cls):
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
        with cls._lock:
            if callback not in cls._callbacks:
                cls._callbacks.append(callback)

    @classmethod
    def register_shutdown_callback(cls, callback: Callable[[], None]):
        cls.register_callback(callback)
