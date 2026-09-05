from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from src.api.routes import (
    accounts_router,
    catalog_router,
    installed_mods_router,
    mod_updates_router,
    settings_router,
    logs_router,
    system_router,
)
from src.database import DatabaseManager
from src.providers import ProviderRegistry
from src.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Démarrage de l'API REST SIMS 4 Mods Manager...")
    DatabaseManager.get_instance()
    ProviderRegistry.initialize()
    yield
    # Shutdown
    logger.info("Arrêt de l'API REST SIMS 4 Mods Manager.")


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application instance."""
    app = FastAPI(
        title="SIMS 4 Mods Manager API",
        description=(
            "API REST unifiée pour piloter l'ensemble des fonctionnalités du gestionnaire de mods Sims 4 : "
            "Catalogue multi-sources, téléchargement, installation, détection, activation/désactivation, "
            "mises à jour en 1 clic, contournement anti-bot et journalisation en temps réel."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routers
    app.include_router(accounts_router.router, prefix="/api")
    app.include_router(catalog_router.router, prefix="/api")
    app.include_router(installed_mods_router.router, prefix="/api")
    app.include_router(mod_updates_router.router, prefix="/api")
    app.include_router(settings_router.router, prefix="/api")
    app.include_router(logs_router.router, prefix="/api")
    app.include_router(system_router.router, prefix="/api")

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/docs")

    return app


app = create_app()
