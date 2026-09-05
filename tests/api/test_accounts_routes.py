from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.database import DatabaseManager


@pytest.fixture
def client():
    DatabaseManager.get_instance()
    with TestClient(app) as c:
        yield c


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
    with patch("src.core.session_manager.SessionManager.clear_session", return_value=True):
        resp = client.delete("/api/accounts/loverslab")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
