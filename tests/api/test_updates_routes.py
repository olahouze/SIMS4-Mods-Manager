from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.database import DatabaseManager, CatalogMod, InstalledMod


@pytest.fixture
def client():
    DatabaseManager.get_instance()
    with TestClient(app) as c:
        yield c


def test_updates_endpoints(client):
    resp = client.get("/api/updates")
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert "items" in data


def test_updates_endpoint_all_installed_and_batch(monkeypatch):
    from src.api.routes import mod_updates_router

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
    monkeypatch.setattr(mod_updates_router, "_update_one_mod", lambda mod_id: (True, f"Mod {mod_id} mis à jour"))
    batch_resp = client.post("/api/updates/batch", json={"installed_ids": [inst1_id]})
    assert batch_resp.status_code == 200
    batch_data = batch_resp.json()
    assert batch_data["success"] is True
