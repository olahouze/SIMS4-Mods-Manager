from collections import OrderedDict
import threading
from typing import Optional
from PySide6.QtGui import QPixmap


class ImageCache:
    """Thread-safe in-memory LRU pixmap cache to avoid redundant disk reads and decoding."""

    _cache: OrderedDict[str, QPixmap] = OrderedDict()
    _max_items: int = 150
    _lock = threading.Lock()

    @classmethod
    def get(cls, key: str) -> Optional[QPixmap]:
        """Retrieves a cached pixmap by key (URL or local path)."""
        with cls._lock:
            if key in cls._cache:
                cls._cache.move_to_end(key)
                return cls._cache[key]
            return None

    @classmethod
    def set(cls, key: str, pixmap: QPixmap) -> None:
        """Stores a pixmap into the LRU cache."""
        if not key or pixmap.isNull():
            return
        with cls._lock:
            cls._cache[key] = pixmap
            cls._cache.move_to_end(key)
            if len(cls._cache) > cls._max_items:
                cls._cache.popitem(last=False)

    @classmethod
    def clear(cls) -> None:
        """Clears all in-memory pixmaps."""
        with cls._lock:
            cls._cache.clear()
