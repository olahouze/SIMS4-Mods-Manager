import httpx
from typing import Optional, Dict, Any, List


class ApiClient:
    """
    HTTP client communicating with the local FastAPI REST server.
    Used by all PySide6 GUI views to guarantee 100% decoupling from core/DB.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")
        # High timeout for long-running actions like interactive login, downloads, sync
        self._client = httpx.Client(base_url=self.base_url, timeout=360.0)

    # --- System & Health ---
    def get_health(self) -> Dict[str, Any]:
        resp = self._client.get("/api/system/health")
        resp.raise_for_status()
        return resp.json()

    # --- Accounts ---
    def get_accounts(self) -> List[Dict[str, Any]]:
        resp = self._client.get("/api/accounts")
        resp.raise_for_status()
        return resp.json().get("accounts", [])

    def test_account(self, provider_name: str) -> Dict[str, Any]:
        resp = self._client.post(f"/api/accounts/{provider_name}/test")
        resp.raise_for_status()
        return resp.json()

    def clear_account(self, provider_name: str) -> Dict[str, Any]:
        resp = self._client.delete(f"/api/accounts/{provider_name}")
        resp.raise_for_status()
        return resp.json()

    def login_account(self, provider_name: str, timeout_seconds: int = 300) -> Dict[str, Any]:
        resp = self._client.post(f"/api/accounts/{provider_name}/login", json={"timeout_seconds": timeout_seconds})
        resp.raise_for_status()
        return resp.json()

    # --- Catalog ---
    def get_catalog(
        self,
        search: Optional[str] = None,
        source: Optional[str] = None,
        access: Optional[str] = None,
        status: Optional[str] = None,
        sort: Optional[str] = "recent",
        page: int = 1,
        limit: int = 100,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "limit": limit}
        if search:
            params["search"] = search
        if source:
            params["source"] = source
        if access:
            params["access"] = access
        if status:
            params["status"] = status
        if sort:
            params["sort"] = sort

        resp = self._client.get("/api/catalog", params=params)
        resp.raise_for_status()
        return resp.json()

    def start_catalog_sync(self, max_pages: int = 5) -> Dict[str, Any]:
        resp = self._client.post("/api/catalog/sync", json={"max_pages": max_pages})
        resp.raise_for_status()
        return resp.json()

    def get_catalog_sync_status(self) -> Dict[str, Any]:
        resp = self._client.get("/api/catalog/sync/status")
        resp.raise_for_status()
        return resp.json()

    def install_mod(
        self,
        catalog_mod_id: Optional[int] = None,
        source: Optional[str] = None,
        remote_id: Optional[str] = None,
        page_url: Optional[str] = None,
        title: Optional[str] = None,
        updated_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "catalog_mod_id": catalog_mod_id,
            "source": source,
            "remote_id": remote_id,
            "page_url": page_url,
            "title": title,
            "updated_date": updated_date,
        }
        resp = self._client.post("/api/catalog/install", json=payload)
        resp.raise_for_status()
        return resp.json()

    def install_mod_stream(self, payload: Dict[str, Any]):
        """Streams real-time progress events from the API during mod installation."""
        import json

        with self._client.stream("POST", "/api/catalog/install-stream", json=payload, timeout=300.0) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    try:
                        yield json.loads(line)
                    except Exception:
                        pass

    def get_catalog_mod_details(self, mod_id: int, force_refresh: bool = False) -> Dict[str, Any]:
        params = {"force_refresh": "true"} if force_refresh else None
        resp = self._client.get(f"/api/catalog/{mod_id}/details", params=params)
        resp.raise_for_status()
        return resp.json()

    # --- Installed Mods ---
    def get_installed_mods(self, search: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if search:
            params["search"] = search
        resp = self._client.get("/api/installed", params=params)
        resp.raise_for_status()
        return resp.json()

    def toggle_mod(self, mod_id: int, enabled: Optional[bool] = None) -> Dict[str, Any]:
        resp = self._client.post(f"/api/installed/{mod_id}/toggle", json={"enabled": enabled})
        resp.raise_for_status()
        return resp.json()

    def uninstall_mod(self, mod_id: int) -> Dict[str, Any]:
        resp = self._client.delete(f"/api/installed/{mod_id}")
        resp.raise_for_status()
        return resp.json()

    def scan_installed_mods(self) -> Dict[str, Any]:
        resp = self._client.post("/api/installed/scan")
        resp.raise_for_status()
        return resp.json()

    def open_folder(self, folder_name: Optional[str] = None) -> Dict[str, Any]:
        resp = self._client.post("/api/installed/open-folder", json={"folder_name": folder_name})
        resp.raise_for_status()
        return resp.json()

    # --- Updates ---
    def get_updates(self) -> Dict[str, Any]:
        resp = self._client.get("/api/updates")
        resp.raise_for_status()
        return resp.json()

    def update_mod(self, installed_id: int) -> Dict[str, Any]:
        resp = self._client.post(f"/api/updates/{installed_id}")
        resp.raise_for_status()
        return resp.json()

    def update_selected_mods(self, installed_ids: List[int]) -> Dict[str, Any]:
        resp = self._client.post("/api/updates/batch", json={"installed_ids": installed_ids})
        resp.raise_for_status()
        return resp.json()

    def update_all_mods(self) -> Dict[str, Any]:
        resp = self._client.post("/api/updates/all")
        resp.raise_for_status()
        return resp.json()

    # --- Settings & Game ---
    def get_settings(self) -> Dict[str, Any]:
        resp = self._client.get("/api/settings")
        resp.raise_for_status()
        return resp.json()

    def update_settings(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._client.patch("/api/settings", json=payload)
        resp.raise_for_status()
        return resp.json()

    def clear_cache(self) -> Dict[str, Any]:
        resp = self._client.post("/api/settings/cache/clear")
        resp.raise_for_status()
        return resp.json()

    def launch_game(self) -> Dict[str, Any]:
        resp = self._client.post("/api/game/launch")
        resp.raise_for_status()
        return resp.json()

    # --- Logs ---
    def get_logs(self, level: Optional[str] = None, search: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit}
        if level:
            params["level"] = level
        if search:
            params["search"] = search
        resp = self._client.get("/api/logs", params=params)
        resp.raise_for_status()
        return resp.json()

    def clear_logs(self) -> Dict[str, Any]:
        resp = self._client.delete("/api/logs")
        resp.raise_for_status()
        return resp.json()

    def open_logs_folder(self) -> Dict[str, Any]:
        resp = self._client.post("/api/logs/open-folder")
        resp.raise_for_status()
        return resp.json()


# Global Singleton Client Instance
_api_client: Optional[ApiClient] = None


def init_api_client(base_url: str = "http://127.0.0.1:8000") -> ApiClient:
    global _api_client
    _api_client = ApiClient(base_url=base_url)
    return _api_client


def get_api_client() -> ApiClient:
    global _api_client
    if _api_client is None:
        _api_client = ApiClient()
    return _api_client
