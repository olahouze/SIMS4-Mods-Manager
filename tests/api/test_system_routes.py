import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.database import DatabaseManager


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


def test_api_ping_endpoint(client):
    resp = client.get("/api/system/ping")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
