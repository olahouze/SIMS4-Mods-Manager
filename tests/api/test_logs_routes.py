import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.database import DatabaseManager


@pytest.fixture
def client():
    DatabaseManager.get_instance()
    with TestClient(app) as c:
        yield c


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
