import pytest
from src.utils.network import find_available_port
from src.api.server import ApiServer
from src.api.client import init_api_client, ApiClient


@pytest.fixture(scope="module")
def live_server():
    free_port = find_available_port("127.0.0.1", start_port=8990)
    ApiServer.start_background(host="127.0.0.1", port=free_port, wait_ready=True)
    client = init_api_client(base_url=f"http://127.0.0.1:{free_port}")
    yield client
    ApiServer.stop()


def test_live_api_client_health(live_server: ApiClient):
    health = live_server.get_health()
    assert health["status"] == "healthy"
    assert "version" in health


def test_live_api_client_accounts(live_server: ApiClient):
    accounts = live_server.get_accounts()
    assert isinstance(accounts, list)
    assert len(accounts) >= 2


def test_live_api_client_catalog(live_server: ApiClient):
    catalog = live_server.get_catalog(limit=5)
    assert "items" in catalog
    assert "total" in catalog


def test_live_api_client_installed(live_server: ApiClient):
    installed = live_server.get_installed_mods()
    assert "items" in installed
    assert "total" in installed


def test_live_api_client_settings(live_server: ApiClient):
    settings = live_server.get_settings()
    assert "theme" in settings
    assert "auto_backup" in settings


def test_live_api_client_logs(live_server: ApiClient):
    logs = live_server.get_logs(limit=10)
    assert "items" in logs
    assert "total" in logs
