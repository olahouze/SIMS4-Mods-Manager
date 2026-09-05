from fastapi import APIRouter
from sqlalchemy import text

from src.api.schemas.system import HealthResponse
from src.core.config import AppConfig
from src.database.manager import DatabaseManager
from src.core.session_manager import SessionManager
from src.services.game_service import GameDetector
from src.utils.logger import logger

router = APIRouter(prefix="/system", tags=["System & Health"])


@router.get("/ping")
def ping():
    """Fast liveness check endpoint returning immediately."""
    return {"status": "ok"}


@router.get("/health", response_model=HealthResponse)
def get_health():
    """Returns overall health, game detection, mods folder status, and browser availability."""
    config = AppConfig.load()
    mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
    exe_path = GameDetector.detect_game_executable(config.custom_game_exe)
    browser_ready = SessionManager.is_browser_available()

    db_ok = False
    try:
        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            session.execute(text("SELECT 1"))
            db_ok = True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        db_ok = AppConfig.get_db_path().exists()

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        game_detected=exe_path is not None and exe_path.exists(),
        mods_dir_detected=mods_dir is not None and mods_dir.exists(),
        mods_dir=str(mods_dir) if mods_dir else None,
        browser_engine_ready=browser_ready,
        database_ok=db_ok,
    )
