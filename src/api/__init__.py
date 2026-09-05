def __getattr__(name: str):
    if name in ("app", "create_app"):
        from src.api.app import app, create_app

        if name == "app":
            return app
        return create_app
    if name in ("ApiClient", "get_api_client", "init_api_client"):
        from src.api.client import ApiClient, get_api_client, init_api_client

        if name == "ApiClient":
            return ApiClient
        if name == "get_api_client":
            return get_api_client
        return init_api_client
    if name == "ApiServer":
        from src.api.server import ApiServer

        return ApiServer
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = ["app", "create_app", "ApiClient", "get_api_client", "init_api_client", "ApiServer"]
