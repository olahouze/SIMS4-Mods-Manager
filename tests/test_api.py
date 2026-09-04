import uuid
import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.core.database import DatabaseManager, CatalogMod, InstalledMod


@pytest.fixture
def client():
    DatabaseManager.get_instance()
    with TestClient(app) as c:
        yield c


def test_system_health(client):
    resp = client.get("/api/system/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "mods_dir_detected" in data


def test_accounts_endpoints(client):
    # List
    resp = client.get("/api/accounts")
    assert resp.status_code == 200
    data = resp.json()
    assert "accounts" in data
    assert len(data["accounts"]) >= 2
    providers = [a["provider_name"] for a in data["accounts"]]
    assert "loverslab" in providers
    assert "patreon" in providers

    # Clear (mocked to protect user session during tests)
    from unittest.mock import patch

    with patch("src.core.session_manager.SessionManager.clear_session", return_value=True):
        resp = client.delete("/api/accounts/loverslab")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


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


def test_updates_endpoints(client):
    resp = client.get("/api/updates")
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert "items" in data


def test_settings_endpoints(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "auto_backup" in data
    assert "backups_dir" in data

    # Patch
    resp = client.patch("/api/settings", json={"theme": "dark", "auto_backup": True})
    assert resp.status_code == 200
    assert resp.json()["theme"] == "dark"

    # Clear cache
    resp = client.post("/api/settings/cache/clear")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_logs_endpoints(client):
    resp = client.get("/api/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data

    # Clear
    resp = client.delete("/api/logs")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


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

