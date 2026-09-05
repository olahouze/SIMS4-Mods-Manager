import uuid
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.database import DatabaseManager, InstalledMod, CatalogMod


@pytest.fixture
def client():
    DatabaseManager.get_instance()
    with TestClient(app) as c:
        yield c


def test_installed_endpoints(client):
    uid = uuid.uuid4().hex[:8]
    remote_id = f"test_inst_{uid}"
    folder_name = f"LoversLab_Installed_{uid}"

    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        inst = InstalledMod(
            source="loverslab",
            remote_id=remote_id,
            title=f"Installed API Mod {uid}",
            folder_name=folder_name,
            is_enabled=True,
        )
        session.add(inst)
        session.commit()
        inst_id = inst.id

    # List
    resp = client.get("/api/installed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    found = next((m for m in data["items"] if m["id"] == inst_id), None)
    assert found is not None

    # Uninstall
    resp = client.delete(f"/api/installed/{inst_id}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_installed_mods_metadata_enrichment(tmp_path, monkeypatch):
    db_path = tmp_path / "test_installed_enrich.db"
    db_mgr = DatabaseManager(str(db_path))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    with db_mgr.get_session() as session:
        # Create CatalogMod
        cmod = CatalogMod(
            source="loverslab",
            remote_id="88888",
            title="Enriched Mod",
            author="ModMaster",
            thumbnail_url="https://example.com/thumb.jpg",
            page_url="https://example.com/mod/88888",
        )
        session.add(cmod)
        session.commit()

        # Create InstalledMod without author/thumbnail
        imod = InstalledMod(
            source="loverslab",
            remote_id="88888",
            title="Enriched Mod",
            folder_name="loverslab_EnrichedMod_123",
            catalog_mod_id=cmod.id,
        )
        session.add(imod)
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


def test_installed_mod_dependents_endpoint(client):
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        # Create prerequisite mod
        prereq_cat = CatalogMod(
            source="loverslab",
            remote_id="prereq_99",
            title="Prerequisite Core Mod",
            page_url="https://example.com/prereq",
        )
        prereq_inst = InstalledMod(
            source="loverslab",
            remote_id="prereq_99",
            title="Prerequisite Core Mod",
            folder_name="prereq_folder",
        )

        # Create dependent mod
        child_cat = CatalogMod(
            source="loverslab",
            remote_id="child_99",
            title="Dependent Child Mod",
            page_url="https://example.com/child",
        )
        child_cat.set_requirements_mods_list([
            {"source": "loverslab", "remote_id": "prereq_99", "title": "Prerequisite Core Mod"}
        ])
        child_inst = InstalledMod(
            source="loverslab",
            remote_id="child_99",
            title="Dependent Child Mod",
            folder_name="child_folder",
        )

        session.add_all([prereq_cat, prereq_inst, child_cat, child_inst])
        session.commit()

        prereq_inst.catalog_mod_id = prereq_cat.id
        child_inst.catalog_mod_id = child_cat.id
        session.commit()

        prereq_id = prereq_inst.id
        child_id = child_inst.id

    # Query dependents endpoint
    resp = client.get(f"/api/installed/{prereq_id}/dependents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_dependents"] is True
    assert data["count"] == 1
    assert data["dependents"][0]["id"] == child_id
    assert data["dependents"][0]["title"] == "Dependent Child Mod"

    # Query child mod dependents (should be empty)
    child_resp = client.get(f"/api/installed/{child_id}/dependents")
    assert child_resp.status_code == 200
    assert child_resp.json()["has_dependents"] is False
    assert child_resp.json()["count"] == 0

