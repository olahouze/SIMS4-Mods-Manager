
from src.ui.components.filter_bar import FilterBar
from src.ui.components.mod_card import ModCard
from src.ui.components.installed_card import InstalledCard
from src.ui.components.progress_dialog import ProgressDialog
from src.ui.components.image_viewer_modal import ImageViewerModal


def test_filter_bar_state_and_signals(qapp):
    fb = FilterBar()
    signals_received = []
    fb.filters_changed.connect(lambda: signals_received.append(True))

    # Set search query
    fb.search_input.setText("wicked")
    assert len(signals_received) >= 1

    # Extract state
    state = fb.get_filter_state()
    assert state["search"] == "wicked"
    assert "source" in state
    assert "mod_type" in state
    assert "status" in state

    # Reset
    fb.reset_filters()
    assert fb.search_input.text() == ""


def test_mod_card_rendering_and_signals(qapp):
    mod_data = {
        "id": 1,
        "source": "loverslab",
        "remote_id": "1001",
        "title": "Animation Pack A",
        "author": "ModderOne",
        "thumbnail_url": "",
        "page_url": "https://example.com/mod1",
        "updated_date": "2026-01-01T00:00:00",
        "patreon_status": "PUBLIC",
        "patreon_tier": "",
        "dependencies": [],
    }

    card = ModCard(mod_data, is_installed=False, has_update=False, is_patreon_auth=True, is_loverslab_auth=True)
    assert card.mod_data["title"] == "Animation Pack A"

    details_called = []
    install_called = []
    card.details_requested.connect(lambda d: details_called.append(d))
    card.install_requested.connect(lambda d: install_called.append(d))

    # Simulate install click
    card.action_btn.click()
    assert len(install_called) == 1
    assert install_called[0]["id"] == 1

    # Already installed state with update
    card_inst = ModCard(mod_data, is_installed=True, has_update=True, is_patreon_auth=True, is_loverslab_auth=True)
    assert any(w in card_inst.action_btn.text().lower() for w in ["jour", "update", "actualiz"])


def test_installed_card_signals(qapp):
    mod_data = {
        "id": 10,
        "source": "loverslab",
        "remote_id": "2002",
        "title": "Installed Clothes",
        "author": "ModderTwo",
        "folder_name": "loverslab_InstalledClothes_123",
        "thumbnail_url": "",
        "is_enabled": True,
        "installed_date": "2026-02-01T00:00:00",
        "files_count": 3,
        "has_update": False,
        "dependencies": [],
    }

    card = InstalledCard(mod_data)
    delete_called = []
    open_folder_called = []
    card.delete_requested.connect(lambda d: delete_called.append(d))
    card.open_folder_requested.connect(lambda folder: open_folder_called.append(folder))

    card.btn_delete.click()
    assert len(delete_called) == 1

    card.btn_folder.click()
    assert len(open_folder_called) == 1
    assert open_folder_called[0] == "loverslab_InstalledClothes_123"


def test_progress_dialog(qapp):
    dlg = ProgressDialog("Downloading Mod", parent=None)
    dlg.set_progress(50)
    dlg.set_status("Extracting files...")
    dlg.set_details("12/24 MB")

    assert dlg.progress_bar.value() == 50
    assert dlg.status_label.text() == "Extracting files..."
    assert dlg.details_label.text() == "12/24 MB"


def test_image_viewer_modal(qapp, monkeypatch):
    images = ["https://example.com/img1.jpg", "https://example.com/img2.jpg"]
    monkeypatch.setattr("src.ui.components.image_viewer_modal.FullImageFetchWorker.start", lambda self: None)
    modal = ImageViewerModal(images, current_index=0)
    assert modal.current_index == 0

    # Next
    modal._on_next()
    assert modal.current_index == 1

    # Prev
    modal._on_prev()
    assert modal.current_index == 0
