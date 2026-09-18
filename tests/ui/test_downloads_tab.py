import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
from bs4 import BeautifulSoup

from src.ui.views.downloads_view import DownloadsView
from src.ui.views.catalog_view import CatalogView
from src.providers.loverslab.downloader import extract_download_candidates


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_downloads_view_init(qapp):
    view = DownloadsView()
    view.show()
    assert view.title_label.text() != ""
    assert len(view.tasks) == 0
    assert not view.empty_widget.isHidden()
    view.close()
    view.deleteLater()


def test_downloads_view_start_download_and_progress(qapp, monkeypatch):
    view = DownloadsView()
    view.show()
    active_counts = []
    view.active_count_changed.connect(lambda c: active_counts.append(c))

    # Mock InstallWorker to avoid actual network/SSE
    mock_worker = MagicMock()
    monkeypatch.setattr("src.ui.views.downloads_view.InstallWorker", lambda mod_data: mock_worker)

    mod_data = {"id": 1234, "title": "Test Mod", "source": "loverslab"}
    task_id = view.start_download(mod_data)

    assert task_id in view.tasks
    assert task_id in view.card_widgets
    assert view.empty_widget.isHidden()
    assert 1 in active_counts

    card = view.card_widgets[task_id]
    assert card.title_label.text() == "Test Mod"

    # Simulate progress update
    view._on_worker_progress(task_id, 50, "Téléchargement en cours...", "1.5 Mo / 3.0 Mo")
    assert card.progress_bar.value() == 50
    assert card.percent_label.text() == "50%"
    assert card.status == "downloading"

    # Simulate finish
    view._on_worker_finished(task_id, True, "Mod installé avec succès")
    assert card.status == "completed"
    assert card.progress_bar.value() == 100
    assert not card.btn_open_folder.isHidden()
    assert 0 in active_counts

    # Test clear finished
    view.clear_finished_downloads()
    assert len(view.tasks) == 0
    assert not view.empty_widget.isHidden()

    view.close()
    view.deleteLater()


def test_downloads_card_cancellation(qapp, monkeypatch):
    view = DownloadsView()
    view.show()
    mock_worker = MagicMock()
    monkeypatch.setattr("src.ui.views.downloads_view.InstallWorker", lambda mod_data: mock_worker)

    mod_data = {"id": 999, "title": "Cancel Mod", "source": "patreon"}
    task_id = view.start_download(mod_data)
    card = view.card_widgets[task_id]

    # Trigger cancel
    card.btn_cancel.click()
    assert card.status == "cancelled"
    assert mock_worker.cancel.called

    view.close()
    view.deleteLater()


def test_catalog_view_non_blocking_download(qapp):
    cat_view = CatalogView()
    cat_view.show()
    cat_view.api_client = MagicMock()
    cat_view.api_client.check_dependencies.return_value = {}

    download_requested_mods = []
    cat_view.download_requested.connect(lambda d: download_requested_mods.append(d))

    mod_data = {"id": 42, "title": "Non-blocking Mod", "source": "loverslab"}
    cat_view.install_mod(mod_data)

    # Verify download_requested was emitted
    assert len(download_requested_mods) == 1
    assert download_requested_mods[0]["title"] == "Non-blocking Mod"

    # Verify toast banner became visible without opening blocking ProgressDialog
    assert hasattr(cat_view, "toast_banner")
    assert not cat_view.toast_banner.isHidden()

    cat_view.close()
    cat_view.deleteLater()


def test_loverslab_candidate_extraction_with_button():
    html = """
    <html>
    <body>
        <div class="ipsDataItem">
            <h4 class="ipsDataItem_title">DD4KriticalsDevices_v1.0.0.zip</h4>
            <div class="ipsDataItem_meta">12.86 kB</div>
            <a href="https://www.loverslab.com/files/file/21924/?do=download&r=123&confirm=1" data-action="download">Download</a>
        </div>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates = extract_download_candidates(soup, "https://www.loverslab.com")
    assert len(candidates) == 1
    assert candidates[0]["title"] == "DD4KriticalsDevices_v1.0.0.zip"
    assert "confirm=1" in candidates[0]["url"]
    assert candidates[0]["score"] >= 150
