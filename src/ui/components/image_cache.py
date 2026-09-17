from collections import OrderedDict
import threading
from typing import Optional
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt


class ImageCache:
    """
    Thread-safe in-memory LRU pixmap cache with memory byte-budgeting and pre-scaled pixmap caching.
    Prevents redundant disk reads, decoding, and CPU scaling operations on the main UI thread.
    """

    _cache: OrderedDict[str, QPixmap] = OrderedDict()
    _byte_sizes: dict[str, int] = {}
    _max_items: int = 300
    _max_bytes: int = 128 * 1024 * 1024  # 128 MB memory budget
    _current_bytes: int = 0
    _lock = threading.Lock()

    @staticmethod
    def _estimate_pixmap_size(pixmap: QPixmap) -> int:
        """Estimates RAM size of a QPixmap in bytes."""
        depth = pixmap.depth() or 32
        bytes_per_pixel = max(1, depth // 8)
        return pixmap.width() * pixmap.height() * bytes_per_pixel

    @classmethod
    def get(cls, key: str) -> Optional[QPixmap]:
        """Retrieves a cached pixmap by key (URL or local path)."""
        if not key:
            return None
        with cls._lock:
            if key in cls._cache:
                cls._cache.move_to_end(key)
                return cls._cache[key]
            return None

    @classmethod
    def get_scaled(cls, key: str, width: int, height: int) -> Optional[QPixmap]:
        """Retrieves a pre-scaled pixmap to avoid expensive scaling on the UI thread."""
        if not key:
            return None
        scaled_key = f"{key}@{width}x{height}"
        return cls.get(scaled_key)

    @classmethod
    def set(cls, key: str, pixmap: QPixmap) -> None:
        """Stores a pixmap into the LRU cache with byte-budget eviction."""
        if not key:
            return

        with cls._lock:
            if pixmap.isNull():
                return
            size = cls._estimate_pixmap_size(pixmap)
            if key in cls._cache:
                cls._current_bytes -= cls._byte_sizes.get(key, 0)

            cls._cache[key] = pixmap
            cls._byte_sizes[key] = size
            cls._current_bytes += size
            cls._cache.move_to_end(key)

            # Evict if exceeding max items or memory budget
            while (len(cls._cache) > cls._max_items or cls._current_bytes > cls._max_bytes) and cls._cache:
                oldest_key, _ = cls._cache.popitem(last=False)
                cls._current_bytes -= cls._byte_sizes.pop(oldest_key, 0)

    @classmethod
    def set_scaled(cls, key: str, width: int, height: int, pixmap: QPixmap) -> None:
        """Stores an already-scaled pixmap."""
        if not key or pixmap.isNull():
            return
        scaled_key = f"{key}@{width}x{height}"
        cls.set(scaled_key, pixmap)

    @classmethod
    def get_or_scale(
        cls,
        key: str,
        width: int,
        height: int,
        aspect_ratio_mode=Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        transformation_mode=Qt.TransformationMode.SmoothTransformation,
    ) -> Optional[QPixmap]:
        """
        Retrieves pre-scaled pixmap from cache, or scales the base cached pixmap,
        caches the scaled version, and returns it.
        """
        if not key:
            return None

        scaled = cls.get_scaled(key, width, height)
        if scaled:
            return scaled

        base = cls.get(key)
        if base and not base.isNull():
            scaled = base.scaled(width, height, aspect_ratio_mode, transformation_mode)
            cls.set_scaled(key, width, height, scaled)
            return scaled

        return None

    @classmethod
    def pop(cls, key: str) -> None:
        """Removes a single key from cache."""
        with cls._lock:
            if key in cls._cache:
                cls._cache.pop(key, None)
                cls._current_bytes -= cls._byte_sizes.pop(key, 0)

    @classmethod
    def clear(cls) -> None:
        """Clears all in-memory pixmaps."""
        with cls._lock:
            cls._cache.clear()
            cls._byte_sizes.clear()
            cls._current_bytes = 0

