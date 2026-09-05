from unittest.mock import MagicMock
from src.services.catalog_sync_service import (
    SyncTracker,
    run_catalog_sync,
    check_catalog_dependencies,
)
from src.database.manager import DatabaseManager
from src.database.models import CatalogMod, InstalledMod
from src.providers import ProviderRegistry


def test_sync_tracker_full_lifecycle():
    categories = [
        {"id": "1", "name": "Cat1", "default_pages": 2},
        {"id": "2", "name": "Cat2", "default_pages": 3},
    ]
    SyncTracker.start(max_pages=5, categories_list=categories)
    assert SyncTracker.is_running is True
    assert SyncTracker.total_pages == 5
    assert len(SyncTracker.categories) == 2
    assert SyncTracker.providers_status["loverslab"] == "RUNNING"

    # Update category progress
    SyncTracker.update_category("1", pages_completed=1, total_pages=2, mods_count=20, status="IN_PROGRESS")
    assert SyncTracker.categories["1"]["pages_completed"] == 1
    assert SyncTracker.categories["1"]["mods_count"] == 20

    # Record page
    SyncTracker.record_page(new_count=20, is_first_page=True)
    assert SyncTracker.total_scraped == 20
    assert SyncTracker.pages_completed == 1
    assert SyncTracker.page1_ready is True
    assert SyncTracker.progress_percent == 20

    # Convert to response
    resp = SyncTracker.to_response()
    assert resp.is_running is True
    assert resp.total_scraped >= 20
    assert resp.progress_percent == 20
    assert len(resp.categories_progress) == 2

    # Stop request
    SyncTracker.stop()
    assert SyncTracker.stop_requested is True

    # Finish
    SyncTracker.finish(total_new=50)
    assert SyncTracker.is_running is False
    assert SyncTracker.progress_percent == 100
    assert SyncTracker.providers_status["loverslab"] == "OK"

    # Fail
    SyncTracker.set_error("Scraping error occurred")
    assert SyncTracker.is_running is False
    assert SyncTracker.has_error is True
    assert SyncTracker.error_message == "Scraping error occurred"


def test_run_catalog_sync_with_mock_provider(tmp_path, monkeypatch):
    db_path = tmp_path / "test_sync_run.db"
    db_mgr = DatabaseManager(str(db_path))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    mock_provider = MagicMock()
    mock_provider.provider_name = "loverslab"
    mock_provider.CATEGORIES = [{"id": "999", "name": "MockCat", "default_pages": 1}]
    mock_provider.scrape_category_page.return_value = (
        [
            {
                "source": "loverslab",
                "remote_id": "synced_mod_1",
                "title": "Synced Mod 1",
                "author": "Author A",
                "category": "MockCat",
                "page_url": "https://example.com/mod1",
                "thumbnail_url": "",
                "published_date": None,
                "updated_date": None,
                "version_str": "1.0",
                "tags": ["sims4"],
                "download_urls": [],
                "external_links": [],
                "patreon_status": "NONE",
                "patreon_tier": "",
                "requirements_text": None,
                "requirements_status": "NONE",
                "requirements_mods": [],
            }
        ],
        1,
    )

    monkeypatch.setattr(ProviderRegistry, "list_providers", classmethod(lambda cls: [mock_provider]))

    SyncTracker.start(max_pages=1, categories_list=mock_provider.CATEGORIES)
    run_catalog_sync(max_pages=1)

    assert SyncTracker.is_running is False
    assert SyncTracker.has_error is False
    assert SyncTracker.total_scraped >= 1

    with db_mgr.get_session() as session:
        m = session.query(CatalogMod).filter_by(remote_id="synced_mod_1").first()
        assert m is not None
        assert m.title == "Synced Mod 1"


def test_check_catalog_dependencies(tmp_path, monkeypatch):
    db_path = tmp_path / "test_chk_deps.db"
    db_mgr = DatabaseManager(str(db_path))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    mock_provider = MagicMock()
    mock_provider.get_mod_details.return_value = {
        "requirements_text": "Requires WickedWhims",
        "requirements_status": "RESOLVED",
        "requirements_mods": [
            {"title": "WickedWhims", "source": "loverslab", "remote_id": "3169", "status": "REQUIRED"}
        ],
    }
    monkeypatch.setattr(ProviderRegistry, "get_provider", classmethod(lambda cls, name: mock_provider))

    # Add catalog mod & installed dependency to DB
    with db_mgr.get_session() as session:
        cat_mod = CatalogMod(
            source="loverslab",
            remote_id="9990",
            title="Test Addon",
            page_url="https://example.com/addon",
            requirements_status="NONE",
        )
        session.add(cat_mod)
        session.add(InstalledMod(source="loverslab", remote_id="3169", title="WickedWhims", folder_name="WW"))
        session.commit()
        session.refresh(cat_mod)

    chk = check_catalog_dependencies(
        mod_title="Test Addon",
        page_url="https://example.com/addon",
        source="loverslab",
        cat_mod=cat_mod,
    )
    assert chk.requirements_status == "RESOLVED"
    assert len(chk.already_installed_dependencies) == 1
    assert chk.already_installed_dependencies[0].title == "WickedWhims"
    assert len(chk.missing_dependencies) == 0
