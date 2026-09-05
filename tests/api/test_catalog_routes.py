import json
import uuid
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.schemas.catalog import CatalogInstallResponse
from src.database import DatabaseManager, CatalogMod


@pytest.fixture
def client():
    DatabaseManager.get_instance()
    with TestClient(app) as c:
        yield c


def test_catalog_endpoints(client):
    uid = uuid.uuid4().hex[:8]
    remote_id = f"test_cat_{uid}"
    title = f"Awesome API Mod {uid}"

    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        mod = CatalogMod(
            source="loverslab",
            remote_id=remote_id,
            title=title,
            author="AuthorAPI",
            category="Clothes",
            page_url="https://loverslab.com/test",
        )
        mod.set_tags_list(["clothing", "female"])
        session.add(mod)
        session.commit()

    resp = client.get(f"/api/catalog?search={uid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(m["remote_id"] == remote_id for m in data["items"])

    # Sync status
    resp = client.get("/api/catalog/sync/status")
    assert resp.status_code == 200
    assert "is_running" in resp.json()


def test_catalog_state_filters(client):
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        session.query(CatalogMod).filter(
            CatalogMod.remote_id.in_(["filter_test_direct", "filter_test_account", "filter_test_sub"])
        ).delete()
        session.commit()

        # Mod direct LoversLab
        m1 = CatalogMod(
            source="loverslab",
            remote_id="filter_test_direct",
            title="Direct Filter Mod",
            author="AuthorDirect",
            page_url="https://loverslab.com/test1",
            patreon_status="NONE",
        )
        # Mod needing account (Patreon)
        m2 = CatalogMod(
            source="loverslab",
            remote_id="filter_test_account",
            title="Account Filter Mod",
            author="AuthorAccount",
            page_url="https://loverslab.com/test2",
            patreon_status="PUBLIC",
        )
        m2.set_tags_list(["Patreon"])
        # Mod needing subscription (Patreon locked)
        m3 = CatalogMod(
            source="loverslab",
            remote_id="filter_test_sub",
            title="Sub Filter Mod",
            author="AuthorSub",
            page_url="https://loverslab.com/test3",
            patreon_status="LOCKED",
            patreon_tier="$5 Tier",
        )
        session.add_all([m1, m2, m3])
        session.commit()

    # Test direct filter
    r_direct = client.get("/api/catalog?access=direct&search=Filter%20Mod")
    assert r_direct.status_code == 200
    direct_ids = [m["remote_id"] for m in r_direct.json()["items"]]
    assert "filter_test_direct" in direct_ids
    assert "filter_test_sub" not in direct_ids

    # Test needs_account filter
    r_acc = client.get("/api/catalog?access=needs_account&search=Filter%20Mod")
    assert r_acc.status_code == 200
    acc_ids = [m["remote_id"] for m in r_acc.json()["items"]]
    assert "filter_test_account" in acc_ids
    assert "filter_test_direct" not in acc_ids

    # Test needs_sub filter
    r_sub = client.get("/api/catalog?access=needs_sub&search=Filter%20Mod")
    assert r_sub.status_code == 200
    sub_ids = [m["remote_id"] for m in r_sub.json()["items"]]
    assert "filter_test_sub" in sub_ids
    assert "filter_test_direct" not in sub_ids
    assert "filter_test_account" not in sub_ids


def test_catalog_sync_default_all_pages(client):
    """Verifies that start sync defaults to max_pages=0 (all pages detected)."""
    with patch("src.api.routes.catalog_router._run_catalog_sync") as mock_sync:
        resp = client.post("/api/catalog/sync", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "is_running" in data
        assert "toutes les pages" in data["message"]
        mock_sync.assert_called_once_with(0)


def test_catalog_mod_details_endpoint(tmp_path, monkeypatch):
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


def test_install_stream_endpoint(monkeypatch):
    from src.api.routes import catalog_router

    def mock_perform_install(payload, progress_callback=None):
        if progress_callback:
            progress_callback(50, "Téléchargement en cours...", "10 Mo • 2 Mo/s")
        return CatalogInstallResponse(success=True, message="Installé avec succès")

    monkeypatch.setattr(catalog_router, "_perform_install", mock_perform_install)

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
