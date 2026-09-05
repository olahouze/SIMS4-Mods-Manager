from pathlib import Path
from fastapi import APIRouter, HTTPException

from src.api.models import (
    SettingsResponse,
    SettingsUpdateRequest,
    ClearCacheResponse,
    LaunchGameResponse,
    DatabaseStatsResponse,
    DatabasePurgeResponse,
)
from src.core.config import AppConfig
from src.core.database import DatabaseManager, CatalogMod, InstalledMod
from src.core.game_detector import GameDetector
from src.utils.logger import logger

router = APIRouter(prefix="", tags=["Settings & Game"])


@router.get("/settings", response_model=SettingsResponse)
def get_settings():
    """Retrieves current application settings and detected directories/paths."""
    config = AppConfig.load()
    detected_mods = GameDetector.detect_mods_dir(config.custom_mods_dir)
    detected_exe = GameDetector.detect_game_executable(config.custom_game_exe)

    return SettingsResponse(
        custom_mods_dir=config.custom_mods_dir,
        custom_game_exe=config.custom_game_exe,
        auto_backup=config.auto_backup,
        adult_content_enabled=config.adult_content_enabled,
        check_updates_on_startup=config.check_updates_on_startup,
        theme=config.theme,
        max_workers=config.max_workers,
        detected_mods_dir=str(detected_mods) if detected_mods else None,
        detected_game_exe=str(detected_exe) if detected_exe else None,
        backups_dir=str(AppConfig.get_backups_dir()),
        thumbnails_cache_dir=str(AppConfig.get_thumbnails_cache_dir()),
        db_path=str(AppConfig.get_db_path()),
        app_dir=str(AppConfig.get_app_dir()),
    )


@router.patch("/settings", response_model=SettingsResponse)
def update_settings(payload: SettingsUpdateRequest):
    """Updates application settings and writes to config.json."""
    config = AppConfig.load()

    if payload.custom_mods_dir is not None:
        config.custom_mods_dir = payload.custom_mods_dir.strip() or None
    if payload.custom_game_exe is not None:
        config.custom_game_exe = payload.custom_game_exe.strip() or None
    if payload.auto_backup is not None:
        config.auto_backup = payload.auto_backup
    if payload.adult_content_enabled is not None:
        config.adult_content_enabled = payload.adult_content_enabled
    if payload.check_updates_on_startup is not None:
        config.check_updates_on_startup = payload.check_updates_on_startup
    if payload.theme is not None:
        config.theme = payload.theme
    if payload.max_workers is not None:
        config.max_workers = payload.max_workers

    config.save()
    logger.info("Paramètres applicatifs mis à jour via l'API.")
    return get_settings()


@router.post("/settings/cache/clear", response_model=ClearCacheResponse)
def clear_cache():
    """Purges cached thumbnails from the local cache directory."""
    cache_dir = AppConfig.get_thumbnails_cache_dir()
    count = 0
    for f in cache_dir.glob("*"):
        try:
            if f.is_file():
                f.unlink()
                count += 1
        except Exception:
            pass

    return ClearCacheResponse(
        success=True,
        message=f"{count} miniature(s) supprimée(s) du cache.",
        deleted_count=count,
    )


@router.post("/game/launch", response_model=LaunchGameResponse)
def launch_game():
    """Launches the Sims 4 game executable via detected or custom path."""
    config = AppConfig.load()
    exe_path = Path(config.custom_game_exe) if config.custom_game_exe else None
    ok = GameDetector.launch_game(exe_path)

    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Impossible de lancer Les Sims 4. Vérifiez le chemin de l'exécutable dans les paramètres.",
        )

    return LaunchGameResponse(success=True, message="Les Sims 4 a été lancé avec succès.")


@router.get("/settings/database/stats", response_model=DatabaseStatsResponse)
def get_database_stats():
    """Returns total counts of catalog mods and installed mods in local database."""
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        cat_count = session.query(CatalogMod).count()
        inst_count = session.query(InstalledMod).count()

    return DatabaseStatsResponse(
        catalog_mods_count=cat_count,
        installed_mods_count=inst_count,
        db_path=str(AppConfig.get_db_path()),
    )


@router.post("/settings/database/purge", response_model=DatabasePurgeResponse)
def purge_database():
    """
    Purges all indexed catalog mods to reset catalog database.
    Does not delete physical files in the user's Sims 4 Mods directory.
    """
    db = DatabaseManager.get_instance()
    deleted = db.purge_catalog()
    return DatabasePurgeResponse(
        success=True,
        deleted_count=deleted,
        message=f"{deleted} mod(s) supprimé(s) du catalogue.",
    )
