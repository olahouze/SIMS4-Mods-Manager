import threading
from PySide6.QtGui import QPixmap, QImage, QColor
from src.ui.components.image_cache import ImageCache


def create_pixmap(color=QColor(255, 0, 0)) -> QPixmap:
    img = QImage(20, 20, QImage.Format.Format_RGB32)
    img.fill(color)
    return QPixmap.fromImage(img)


def test_image_cache_get_set_clear(qapp):
    ImageCache.clear()

    pix = create_pixmap()
    ImageCache.set("http://test.com/1.jpg", pix)

    retrieved = ImageCache.get("http://test.com/1.jpg")
    assert retrieved is not None
    assert not retrieved.isNull()

    assert ImageCache.get("http://nonexistent.com/2.jpg") is None

    ImageCache.clear()
    assert ImageCache.get("http://test.com/1.jpg") is None


def test_image_cache_lru_eviction(qapp, monkeypatch):
    ImageCache.clear()
    monkeypatch.setattr(ImageCache, "_max_items", 2)

    pix1 = create_pixmap(QColor(255, 0, 0))
    pix2 = create_pixmap(QColor(0, 255, 0))
    pix3 = create_pixmap(QColor(0, 0, 255))

    ImageCache.set("key1", pix1)
    ImageCache.set("key2", pix2)
    assert ImageCache.get("key1") is not None

    # Adding 3rd item should evict key2 (since key1 was accessed more recently)
    ImageCache.set("key3", pix3)
    assert ImageCache.get("key1") is not None
    assert ImageCache.get("key3") is not None
    assert ImageCache.get("key2") is None


def test_image_cache_concurrent_access(qapp):
    ImageCache.clear()
    pix = create_pixmap()

    def worker(worker_id):
        for i in range(50):
            ImageCache.set(f"key_{worker_id}_{i}", pix)
            ImageCache.get(f"key_{worker_id}_{i}")

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # ImageCache remained thread-safe and didn't crash
    ImageCache.clear()
