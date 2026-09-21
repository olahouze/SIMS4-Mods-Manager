from PySide6.QtGui import QPixmap, QImage

from src.ui.components.dependencies_summary_widget import DependenciesSummaryWidget
from src.ui.components.image_cache import ImageCache
from src.ui.utils.dialog_helper import DialogHelper


def test_dependencies_summary_widget_rendering(qapp):
    deps = [
        {"title": "WickedWhims", "is_installed": True, "status": "INSTALLED"},
        {"title": "Get To Work", "is_installed": False, "is_game_dlc": True, "status": "GAME_DLC"},
        {"title": "Extra Mod", "is_installed": False, "status": "DETECTED_NOT_INSTALLED"},
    ]
    widget = DependenciesSummaryWidget(dependencies=deps, max_show=2)
    widget.show()
    assert widget.isVisible() is True
    # Should display 2 items plus 1 overflow pill (+1)
    assert widget.layout().count() >= 3

    # Empty list should explicitly hide widget
    empty_widget = DependenciesSummaryWidget(dependencies=[])
    assert empty_widget.isVisible() is False


def test_image_cache_scaled_caching_and_budget(qapp):
    # Create dummy 100x100 pixmap
    img = QImage(100, 100, QImage.Format.Format_RGB32)
    img.fill(0x00FF00)
    pix = QPixmap.fromImage(img)

    ImageCache.set("test_key_base", pix)
    ImageCache.set_scaled("test_scaled_key", 100, 100, pix)
    cached_pix = ImageCache.get_scaled("test_scaled_key", 100, 100)
    assert cached_pix is not None
    assert cached_pix.width() == 100
    assert cached_pix.height() == 100

    # Test get_or_scale
    scaled_pix = ImageCache.get_or_scale("test_key_base", 50, 50)
    assert scaled_pix is not None
    assert scaled_pix.width() == 50 or scaled_pix.height() == 50

    # Fetch again from memory
    hit_pix = ImageCache.get_scaled("test_key_base", 50, 50)
    assert hit_pix is not None


def test_dialog_helper_dialog_creation(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)

    # Test confirmation
    res = DialogHelper.confirm(
        parent=None,
        title="Test Confirm",
        message="Are you sure?",
    )
    assert isinstance(res, bool)
