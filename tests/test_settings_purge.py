from fastapi.testclient import TestClient
from src.api.app import app
from src.core.database import DatabaseManager, CatalogMod, InstalledMod


def test_database_stats_and_purge_endpoints():
    client = TestClient(app)
    db = DatabaseManager.get_instance()

    with db.get_session() as session:
        # Add test catalog mods and installed mod
        cm = CatalogMod(
            source="loverslab",
            remote_id="purge_test_1",
            title="Purge Test Mod",
            page_url="https://loverslab.com/files/file/purge_test_1/",
        )
        session.add(cm)
        session.commit()

        im = InstalledMod(
            catalog_mod_id=cm.id,
            source="loverslab",
            remote_id="purge_test_1",
            title="Purge Test Mod",
            folder_name="purge_mod",
        )
        session.add(im)
        session.commit()

    # 1. Test GET /api/settings/database/stats
    stats_res = client.get("/api/settings/database/stats")
    assert stats_res.status_code == 200
    stats_data = stats_res.json()
    assert stats_data["catalog_mods_count"] >= 1
    assert stats_data["installed_mods_count"] >= 1
    assert "db_path" in stats_data

    # 2. Test POST /api/settings/database/purge
    purge_res = client.post("/api/settings/database/purge")
    assert purge_res.status_code == 200
    purge_data = purge_res.json()
    assert purge_data["success"] is True
    assert purge_data["deleted_count"] >= 1
    assert "supprimé" in purge_data["message"]

    # 3. Verify database state after purge
    with db.get_session() as session:
        # Catalog must be empty
        cat_count = session.query(CatalogMod).count()
        assert cat_count == 0

        # Installed mod must still exist, but catalog_mod_id must be unlinked (None)
        remaining_im = session.query(InstalledMod).filter_by(remote_id="purge_test_1").first()
        assert remaining_im is not None
        assert remaining_im.catalog_mod_id is None

        # Clean up test installed mod
        session.delete(remaining_im)
        session.commit()

    # 4. Re-check stats after purge
    stats_after = client.get("/api/settings/database/stats").json()
    assert stats_after["catalog_mods_count"] == 0
