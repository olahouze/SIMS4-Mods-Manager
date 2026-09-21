import httpx
from typing import Optional, Dict, Any, List, Union


class ApiClient:
    """
    HTTP client communicating with the local FastAPI REST server.
    Used by all PySide6 GUI views to guarantee 100% decoupling from core/DB.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8000", token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        from src.core.security import get_internal_token

        self.token = token or get_internal_token()
        headers = {}
        if self.token:
            headers["X-Internal-Token"] = self.token
        # High timeout for long-running actions like interactive login, downloads, sync
        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=360.0)

    def close(self) -> None:
        """Closes the underlying httpx.Client and releases connection resources."""
        self._client.close()

    @property
    def client(self) -> httpx.Client:
        """Exécute l'opération client.

        Returns:
            Résultat de l'opération client.
        """
        return self._client

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # --- System & Health ---
    def get_health(self) -> Dict[str, Any]:
        """Exécute l'opération get health.

        Returns:
            Résultat de l'opération get_health.
        """
        resp = self._client.get("/api/system/health")
        resp.raise_for_status()
        return resp.json()

    # --- Accounts ---
    def get_accounts(self) -> List[Dict[str, Any]]:
        """Exécute l'opération get accounts.

        Returns:
            Résultat de l'opération get_accounts.
        """
        resp = self._client.get("/api/accounts")
        resp.raise_for_status()
        return resp.json().get("accounts", [])

    def test_account(self, provider_name: str) -> Dict[str, Any]:
        """Exécute l'opération test account.

        Args:
            provider_name: Paramètre provider_name.

        Returns:
            Résultat de l'opération test_account.
        """
        resp = self._client.post(f"/api/accounts/{provider_name}/test")
        resp.raise_for_status()
        return resp.json()

    def clear_account(self, provider_name: str) -> Dict[str, Any]:
        """Exécute l'opération clear account.

        Args:
            provider_name: Paramètre provider_name.

        Returns:
            Résultat de l'opération clear_account.
        """
        resp = self._client.delete(f"/api/accounts/{provider_name}")
        resp.raise_for_status()
        return resp.json()

    def login_account(self, provider_name: str, timeout_seconds: int = 300) -> Dict[str, Any]:
        """Exécute l'opération login account.

        Args:
            provider_name: Paramètre provider_name.
            timeout_seconds: Paramètre timeout_seconds.

        Returns:
            Résultat de l'opération login_account.
        """
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
        mod_type: Optional[str] = None,
        sort: Optional[str] = "recent",
        page: int = 1,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Exécute l'opération get catalog.

        Args:
            search: Paramètre search.
            source: Paramètre source.
            access: Paramètre access.
            status: Paramètre status.
            mod_type: Paramètre mod_type.
            sort: Paramètre sort.
            page: Paramètre page.
            limit: Paramètre limit.

        Returns:
            Résultat de l'opération get_catalog.
        """
        params: Dict[str, Any] = {"page": page, "limit": limit}
        if search:
            params["search"] = search
        if source:
            params["source"] = source
        if access:
            params["access"] = access
        if status:
            params["status"] = status
        if mod_type:
            params["mod_type"] = mod_type
        if sort:
            params["sort"] = sort

        resp = self._client.get("/api/catalog", params=params)
        resp.raise_for_status()
        return resp.json()

    def start_catalog_sync(self, max_pages: int = 0) -> Dict[str, Any]:
        """Exécute l'opération start catalog sync.

        Args:
            max_pages: Paramètre max_pages.

        Returns:
            Résultat de l'opération start_catalog_sync.
        """
        resp = self._client.post("/api/catalog/sync", json={"max_pages": max_pages})
        resp.raise_for_status()
        return resp.json()

    def get_catalog_sync_status(self) -> Dict[str, Any]:
        """Exécute l'opération get catalog sync status.

        Returns:
            Résultat de l'opération get_catalog_sync_status.
        """
        resp = self._client.get("/api/catalog/sync/status")
        resp.raise_for_status()
        return resp.json()

    def pause_catalog_sync(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """Exécute l'opération pause catalog sync.

        Args:
            provider: Paramètre provider.

        Returns:
            Résultat de l'opération pause_catalog_sync.
        """
        params = {"provider": provider} if provider else None
        resp = self._client.post("/api/catalog/sync/pause", params=params)
        resp.raise_for_status()
        return resp.json()

    def resume_catalog_sync(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """Exécute l'opération resume catalog sync.

        Args:
            provider: Paramètre provider.

        Returns:
            Résultat de l'opération resume_catalog_sync.
        """
        params = {"provider": provider} if provider else None
        resp = self._client.post("/api/catalog/sync/resume", params=params)
        resp.raise_for_status()
        return resp.json()

    def stop_catalog_sync(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """Exécute l'opération stop catalog sync.

        Args:
            provider: Paramètre provider.

        Returns:
            Résultat de l'opération stop_catalog_sync.
        """
        params = {"provider": provider} if provider else None
        resp = self._client.post("/api/catalog/sync/stop", params=params)
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
        install_dependencies: bool = True,
        allow_partial: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Exécute l'opération install mod.

        Args:
            catalog_mod_id: Paramètre catalog_mod_id.
            source: Paramètre source.
            remote_id: Paramètre remote_id.
            page_url: Paramètre page_url.
            title: Paramètre title.
            updated_date: Paramètre updated_date.
            install_dependencies: Paramètre install_dependencies.
            allow_partial: Paramètre allow_partial.

        Returns:
            Résultat de l'opération install_mod.
        """
        payload = {
            "catalog_mod_id": catalog_mod_id,
            "source": source,
            "remote_id": remote_id,
            "page_url": page_url,
            "title": title,
            "updated_date": updated_date,
            "install_dependencies": install_dependencies,
            "allow_partial": allow_partial,
        }
        payload.update(kwargs)
        resp = self._client.post("/api/catalog/install", json=payload)
        resp.raise_for_status()
        return resp.json()

    def check_dependencies(self, payload: Union[Dict[str, Any], int, str]) -> Dict[str, Any]:
        """Exécute l'opération check dependencies.

        Args:
            payload: Paramètre payload.

        Returns:
            Résultat de l'opération check_dependencies.
        """
        body: Dict[str, Any]
        if isinstance(payload, int) or (isinstance(payload, str) and payload.isdigit()):
            body = {"catalog_mod_id": int(payload)}
        elif isinstance(payload, dict):
            body = payload
        else:
            body = {"remote_id": str(payload)}
        resp = self._client.post("/api/catalog/check-dependencies", json=body)
        resp.raise_for_status()
        return resp.json()

    def check_missing_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute l'opération check missing report.

        Args:
            payload: Paramètre payload.

        Returns:
            Résultat de l'opération check_missing_report.
        """
        resp = self._client.post("/api/catalog/check-missing-report", json=payload)
        resp.raise_for_status()
        return resp.json()

    def report_missing_requirements(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute l'opération report missing requirements.

        Args:
            payload: Paramètre payload.

        Returns:
            Résultat de l'opération report_missing_requirements.
        """
        resp = self._client.post("/api/catalog/report-missing-requirements", json=payload)
        resp.raise_for_status()
        return resp.json()

    def save_requirements_override(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute l'opération save requirements override.

        Args:
            payload: Paramètre payload.

        Returns:
            Résultat de l'opération save_requirements_override.
        """
        resp = self._client.post("/api/catalog/requirements-override", json=payload)
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
        """Exécute l'opération get catalog mod details.

        Args:
            mod_id: Paramètre mod_id.
            force_refresh: Paramètre force_refresh.

        Returns:
            Résultat de l'opération get_catalog_mod_details.
        """
        params = {"force_refresh": "true"} if force_refresh else None
        resp = self._client.get(f"/api/catalog/{mod_id}/details", params=params)
        resp.raise_for_status()
        return resp.json()

    # --- Installed Mods ---
    def get_installed_mods(self, search: Optional[str] = None) -> Dict[str, Any]:
        """Exécute l'opération get installed mods.

        Args:
            search: Paramètre search.

        Returns:
            Résultat de l'opération get_installed_mods.
        """
        params = {}
        if search:
            params["search"] = search
        resp = self._client.get("/api/installed", params=params)
        resp.raise_for_status()
        return resp.json()

    def toggle_mod(self, mod_id: int, enabled: Optional[bool] = None) -> Dict[str, Any]:
        """Exécute l'opération toggle mod.

        Args:
            mod_id: Paramètre mod_id.
            enabled: Paramètre enabled.

        Returns:
            Résultat de l'opération toggle_mod.
        """
        resp = self._client.post(f"/api/installed/{mod_id}/toggle", json={"enabled": enabled})
        resp.raise_for_status()
        return resp.json()

    def get_mod_dependents(self, mod_id: int) -> Dict[str, Any]:
        """Exécute l'opération get mod dependents.

        Args:
            mod_id: Paramètre mod_id.

        Returns:
            Résultat de l'opération get_mod_dependents.
        """
        resp = self._client.get(f"/api/installed/{mod_id}/dependents")
        resp.raise_for_status()
        return resp.json()

    def uninstall_mod(self, mod_id: int) -> Dict[str, Any]:
        """Exécute l'opération uninstall mod.

        Args:
            mod_id: Paramètre mod_id.

        Returns:
            Résultat de l'opération uninstall_mod.
        """
        resp = self._client.delete(f"/api/installed/{mod_id}")
        resp.raise_for_status()
        return resp.json()

    def scan_installed_mods(self) -> Dict[str, Any]:
        """Exécute l'opération scan installed mods.

        Returns:
            Résultat de l'opération scan_installed_mods.
        """
        resp = self._client.post("/api/installed/scan")
        resp.raise_for_status()
        return resp.json()

    def open_folder(self, folder_name: Optional[str] = None) -> Dict[str, Any]:
        """Exécute l'opération open folder.

        Args:
            folder_name: Paramètre folder_name.

        Returns:
            Résultat de l'opération open_folder.
        """
        resp = self._client.post("/api/installed/open-folder", json={"folder_name": folder_name})
        resp.raise_for_status()
        return resp.json()

    # --- Updates ---
    def get_updates(self) -> Dict[str, Any]:
        """Exécute l'opération get updates.

        Returns:
            Résultat de l'opération get_updates.
        """
        resp = self._client.get("/api/updates")
        resp.raise_for_status()
        return resp.json()

    def update_mod(self, installed_id: int) -> Dict[str, Any]:
        """Exécute l'opération update mod.

        Args:
            installed_id: Paramètre installed_id.

        Returns:
            Résultat de l'opération update_mod.
        """
        resp = self._client.post(f"/api/updates/{installed_id}")
        resp.raise_for_status()
        return resp.json()

    def update_selected_mods(self, installed_ids: List[int]) -> Dict[str, Any]:
        """Exécute l'opération update selected mods.

        Args:
            installed_ids: Paramètre installed_ids.

        Returns:
            Résultat de l'opération update_selected_mods.
        """
        resp = self._client.post("/api/updates/batch", json={"installed_ids": installed_ids})
        resp.raise_for_status()
        return resp.json()

    def update_all_mods(self) -> Dict[str, Any]:
        """Exécute l'opération update all mods.

        Returns:
            Résultat de l'opération update_all_mods.
        """
        resp = self._client.post("/api/updates/all")
        resp.raise_for_status()
        return resp.json()

    # --- Settings & Game ---
    def get_settings(self) -> Dict[str, Any]:
        """Exécute l'opération get settings.

        Returns:
            Résultat de l'opération get_settings.
        """
        resp = self._client.get("/api/settings")
        resp.raise_for_status()
        return resp.json()

    def update_settings(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute l'opération update settings.

        Args:
            payload: Paramètre payload.

        Returns:
            Résultat de l'opération update_settings.
        """
        resp = self._client.patch("/api/settings", json=payload)
        resp.raise_for_status()
        return resp.json()

    def clear_cache(self) -> Dict[str, Any]:
        """Exécute l'opération clear cache.

        Returns:
            Résultat de l'opération clear_cache.
        """
        resp = self._client.post("/api/settings/cache/clear")
        resp.raise_for_status()
        return resp.json()

    def launch_game(self) -> Dict[str, Any]:
        """Exécute l'opération launch game.

        Returns:
            Résultat de l'opération launch_game.
        """
        resp = self._client.post("/api/game/launch")
        resp.raise_for_status()
        return resp.json()

    def get_database_stats(self) -> Dict[str, Any]:
        """Exécute l'opération get database stats.

        Returns:
            Résultat de l'opération get_database_stats.
        """
        resp = self._client.get("/api/settings/database/stats")
        resp.raise_for_status()
        return resp.json()

    def purge_database(self) -> Dict[str, Any]:
        """Exécute l'opération purge database.

        Returns:
            Résultat de l'opération purge_database.
        """
        resp = self._client.post("/api/settings/database/purge")
        resp.raise_for_status()
        return resp.json()

    # --- Logs ---
    def get_logs(self, level: Optional[str] = None, search: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
        """Exécute l'opération get logs.

        Args:
            level: Paramètre level.
            search: Paramètre search.
            limit: Paramètre limit.

        Returns:
            Résultat de l'opération get_logs.
        """
        params: Dict[str, Any] = {"limit": limit}
        if level:
            params["level"] = level
        if search:
            params["search"] = search
        resp = self._client.get("/api/logs", params=params)
        resp.raise_for_status()
        return resp.json()

    def clear_logs(self) -> Dict[str, Any]:
        """Exécute l'opération clear logs.

        Returns:
            Résultat de l'opération clear_logs.
        """
        resp = self._client.delete("/api/logs")
        resp.raise_for_status()
        return resp.json()

    def open_logs_folder(self) -> Dict[str, Any]:
        """Exécute l'opération open logs folder.

        Returns:
            Résultat de l'opération open_logs_folder.
        """
        resp = self._client.post("/api/logs/open-folder")
        resp.raise_for_status()
        return resp.json()


# Global Singleton Client Instance
_api_client: Optional[ApiClient] = None


def init_api_client(base_url: str = "http://127.0.0.1:8000", token: Optional[str] = None) -> ApiClient:
    """Initialise le client HTTP global avec l'URL de base et le jeton de sécurité interne."""
    global _api_client
    _api_client = ApiClient(base_url=base_url, token=token)
    return _api_client


def get_api_client() -> ApiClient:
    """Exécute l'opération get api client.

    Returns:
        Résultat de l'opération get_api_client.
    """
    global _api_client
    if _api_client is None:
        _api_client = ApiClient()
    return _api_client
