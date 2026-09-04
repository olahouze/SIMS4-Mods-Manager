import re
from fastapi.testclient import TestClient

from src.core.mod_installer import sanitize_mod_folder_name, generate_unique_mod_folder_name
from src.core.config import AppConfig
from src.core.game_detector import GameDetector
from src.api.app import app


def test_sanitize_mod_folder_name():
    # 1. Strips spaces and replaces with underscores
    assert sanitize_mod_folder_name("My Great Mod") == "My_Great_Mod"

    # 2. Strips apostrophes
    assert sanitize_mod_folder_name("Kritical's Dreams") == "Kriticals_Dreams"
    assert sanitize_mod_folder_name("L’Armure d’or") == "LArmure_dor"

    # 3. Strips accents / diacritics
    assert sanitize_mod_folder_name("Objekte / Deutsche Übersetzungen") == "Objekte_Deutsche_Ubersetzungen"
    assert sanitize_mod_folder_name("Épée et château") == "Epee_et_chateau"

    # 4. Strips emojis and special symbols
    assert sanitize_mod_folder_name("Cowboy Hat - Pose Pack 🎀") == "Cowboy_Hat_Pose_Pack"
    assert sanitize_mod_folder_name("NEW ❤️ leather Trench") == "NEW_leather_Trench"

    # 5. Strict alphanumeric check: no characters other than [a-zA-Z0-9_]
    res = sanitize_mod_folder_name("Mod! @#$%^&*()_+~`=-[]\\{}|;':\",./<>?")
    assert re.match(r"^[a-zA-Z0-9_]+$", res) is not None


def test_generate_unique_mod_folder_name():
    source = "loverslab"
    title = "Kritical's Dreams of Surrender & Objekte / Deutsche Übersetzungen"
    folder = generate_unique_mod_folder_name(source, title)

    # Pure alphanumeric + underscores
    assert re.match(r"^[a-zA-Z0-9_]+$", folder) is not None
    # Must end with _xxx (3 or 4 digits)
    assert re.search(r"_\d{3,4}$", folder) is not None
    # Must start with source
    assert folder.startswith("loverslab_")
    # Must NOT contain spaces, apostrophes or accents
    assert " " not in folder
    assert "'" not in folder
    assert "’" not in folder
    assert "ü" not in folder
    assert "Ü" not in folder


def test_api_ping_endpoint():
    client = TestClient(app)
    resp = client.get("/api/system/ping")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_app_config_cached_paths(tmp_path):
    cfg = AppConfig(cached_mods_dir=str(tmp_path / "Mods"), cached_game_exe=str(tmp_path / "TS4_x64.exe"))
    assert cfg.cached_mods_dir == str(tmp_path / "Mods")
    assert cfg.cached_game_exe == str(tmp_path / "TS4_x64.exe")


def test_game_detector_cache():
    GameDetector.clear_cache()
    # Cache should start None
    assert GameDetector._cached_mods_dir is None
    assert GameDetector._cached_game_exe is None


def test_cleanup_deleted_mods(tmp_path, monkeypatch):
    from src.core.mod_installer import ModInstaller
    from src.core.database import DatabaseManager, InstalledMod

    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir()
    existing_mod_folder = mods_dir / "loverslab_TestMod_123"
    existing_mod_folder.mkdir()
    (existing_mod_folder / "test.package").write_text("dummy")

    db_path = tmp_path / "test.db"
    db_mgr = DatabaseManager(str(db_path))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    config = AppConfig(custom_mods_dir=str(mods_dir))
    monkeypatch.setattr(AppConfig, "load", classmethod(lambda cls: config))

    # Add two records: one folder exists, one folder was deleted by user
    with db_mgr.get_session() as session:
        session.add(InstalledMod(title="Test Mod 1", folder_name="loverslab_TestMod_123"))
        session.add(InstalledMod(title="Deleted Mod 2", folder_name="loverslab_DeletedMod_456"))
        session.commit()

    # Run cleanup
    removed = ModInstaller.verify_and_cleanup_installed_mods()
    assert "Deleted Mod 2" in removed

    with db_mgr.get_session() as session:
        remaining = session.query(InstalledMod).all()
        assert len(remaining) == 1
        assert remaining[0].title == "Test Mod 1"


def test_clean_and_repair_catalog(tmp_path, monkeypatch):
    from src.core.database import DatabaseManager, CatalogMod

    db_path = tmp_path / "test_repair.db"
    db_mgr = DatabaseManager(str(db_path))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    with db_mgr.get_session() as session:
        # Ghost mod
        session.add(
            CatalogMod(
                source="loverslab",
                remote_id="51260",
                title="",
                author="dohmra",
                page_url="https://www.loverslab.com/files/file/51260-sims-4-mods-vault/",
            )
        )
        # Empty title mod that should be repaired
        session.add(
            CatalogMod(
                source="loverslab",
                remote_id="49558",
                title="",
                author="Frissons",
                page_url="https://www.loverslab.com/files/file/49558-sims-4-frissons-animations-for-wickedwhims-upcoming-september-6th/",
            )
        )
        session.commit()

    db_mgr.clean_and_repair_catalog()

    with db_mgr.get_session() as session:
        ghost = session.query(CatalogMod).filter_by(remote_id="51260").first()
        assert ghost is None  # Ghost must be purged

        repaired = session.query(CatalogMod).filter_by(remote_id="49558").first()
        assert repaired is not None
        assert "Frissons" in repaired.title
        assert repaired.title != ""


def test_catalog_mod_details_endpoint(tmp_path, monkeypatch):
    from src.core.database import DatabaseManager, CatalogMod

    db_path = tmp_path / "test_details.db"
    db_mgr = DatabaseManager(str(db_path))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    mod_id = None
    with db_mgr.get_session() as session:
        mod = CatalogMod(
            source="loverslab",
            remote_id="99999",
            title="Detailed Mod Test",
            author="AuthorTest",
            page_url="https://www.loverslab.com/files/file/99999-test/",
            description="<p>This is a detailed description of the mod.</p>",
            version_str="1.2.0",
        )
        session.add(mod)
        session.commit()
        mod_id = mod.id

    client = TestClient(app)
    resp = client.get(f"/api/catalog/{mod_id}/details")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == mod_id
    assert data["title"] == "Detailed Mod Test"
    assert "detailed description" in data["description"]
    assert data["author"] == "AuthorTest"


def test_installed_mods_metadata_enrichment(tmp_path, monkeypatch):
    from src.core.database import DatabaseManager, CatalogMod, InstalledMod

    db_path = tmp_path / "test_installed_enrich.db"
    db_mgr = DatabaseManager(str(db_path))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    with db_mgr.get_session() as session:
        cat_mod = CatalogMod(
            source="loverslab",
            remote_id="88888",
            title="Enriched Mod",
            author="ModMaster",
            thumbnail_url="https://example.com/thumb.jpg",
            page_url="https://example.com/mod/88888",
        )
        session.add(cat_mod)
        session.commit()

        inst_mod = InstalledMod(
            catalog_mod_id=cat_mod.id,
            source="loverslab",
            remote_id="88888",
            title="Enriched Mod",
            folder_name="loverslab_EnrichedMod_123",
        )
        session.add(inst_mod)
        session.commit()

    client = TestClient(app)
    resp = client.get("/api/installed")
    assert resp.status_code == 200
    data = resp.json()
    items = data.get("items", [])
    assert len(items) >= 1
    target = next((m for m in items if m["folder_name"] == "loverslab_EnrichedMod_123"), None)
    assert target is not None
    assert target["author"] == "ModMaster"
    assert target["thumbnail_url"] == "https://example.com/thumb.jpg"
    assert target["page_url"] == "https://example.com/mod/88888"


def test_install_stream_endpoint(monkeypatch):
    import json
    from src.api.routes import catalog
    from src.api.models import CatalogInstallResponse

    def mock_perform_install(payload, progress_callback=None):
        if progress_callback:
            progress_callback(50, "Téléchargement en cours...", "10 Mo • 2 Mo/s")
        return CatalogInstallResponse(success=True, message="Installé avec succès")

    monkeypatch.setattr(catalog, "_perform_install", mock_perform_install)

    client = TestClient(app)
    resp = client.post(
        "/api/catalog/install-stream",
        json={"catalog_mod_id": 1, "source": "loverslab", "remote_id": "123", "title": "Stream Mod"},
    )
    assert resp.status_code == 200
    lines = [json.loads(line) for line in resp.text.strip().split("\n") if line.strip()]
    assert len(lines) >= 2
    assert any(line.get("type") == "progress" and line.get("percent") == 50 for line in lines)
    assert any(line.get("type") == "finished" and line.get("success") is True for line in lines)


def test_updates_endpoint_all_installed_and_batch(monkeypatch):
    from datetime import datetime, timedelta
    from src.core.database import DatabaseManager, CatalogMod, InstalledMod
    from src.api.routes import updates

    db = DatabaseManager.get_instance()
    now = datetime.now()
    with db.get_session() as session:
        session.query(InstalledMod).filter(InstalledMod.remote_id.in_(["99991", "99992"])).delete()
        session.query(CatalogMod).filter(CatalogMod.remote_id.in_(["99991", "99992"])).delete()
        session.commit()

        # Create a catalog mod with recent updated_date
        cat_mod = CatalogMod(
            source="loverslab",
            remote_id="99991",
            title="Updatable Test Mod",
            author="TestAuthor",
            page_url="https://example.com/mod99991",
            updated_date=now + timedelta(days=1),
            version_str="2.0.0",
        )
        session.add(cat_mod)
        session.commit()

        # Create installed mod with older date
        inst_mod1 = InstalledMod(
            source="loverslab",
            remote_id="99991",
            title="Updatable Test Mod",
            folder_name="loverslab_Updatable_999",
            version_date=now - timedelta(days=1),
            version_str="1.0.0",
        )
        # Create another installed mod with latest date (up to date)
        inst_mod2 = InstalledMod(
            source="loverslab",
            remote_id="99992",
            title="Up-to-Date Mod",
            folder_name="loverslab_UpToDate_999",
            version_date=now,
            version_str="1.5.0",
        )
        session.add_all([inst_mod1, inst_mod2])
        session.commit()
        inst1_id = inst_mod1.id
        inst2_id = inst_mod2.id

    client = TestClient(app)
    resp = client.get("/api/updates")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total_installed"] >= 2
    assert data["count"] >= 1

    item1 = next((m for m in data["items"] if m["installed_id"] == inst1_id), None)
    assert item1 is not None
    assert item1["has_update"] is True
    assert item1["current_version"] == "1.0.0"
    assert item1["new_version"] == "2.0.0"

    item2 = next((m for m in data["items"] if m["installed_id"] == inst2_id), None)
    assert item2 is not None
    assert item2["has_update"] is False

    # Test batch update endpoint with mock
    monkeypatch.setattr(updates, "_update_one_mod", lambda mod_id: (True, f"Mod {mod_id} mis à jour"))
    batch_resp = client.post("/api/updates/batch", json={"installed_ids": [inst1_id]})
    assert batch_resp.status_code == 200
    batch_data = batch_resp.json()
    assert batch_data["success"] is True
    assert batch_data["updated_count"] == 1
    assert batch_data["total_count"] == 1

    # Cleanup
    with db.get_session() as session:
        session.query(InstalledMod).filter(InstalledMod.remote_id.in_(["99991", "99992"])).delete()
        session.query(CatalogMod).filter(CatalogMod.remote_id.in_(["99991", "99992"])).delete()
        session.commit()


