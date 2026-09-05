from typing import Optional
from pydantic import BaseModel


class SettingsResponse(BaseModel):
    custom_mods_dir: Optional[str] = None
    custom_game_exe: Optional[str] = None
    auto_backup: bool
    adult_content_enabled: bool
    check_updates_on_startup: bool
    theme: str
    max_workers: int
    detected_mods_dir: Optional[str] = None
    detected_game_exe: Optional[str] = None
    backups_dir: str
    thumbnails_cache_dir: str
    db_path: str
    app_dir: str


class SettingsUpdateRequest(BaseModel):
    custom_mods_dir: Optional[str] = None
    custom_game_exe: Optional[str] = None
    auto_backup: Optional[bool] = None
    adult_content_enabled: Optional[bool] = None
    check_updates_on_startup: Optional[bool] = None
    theme: Optional[str] = None
    max_workers: Optional[int] = None


class ClearCacheResponse(BaseModel):
    success: bool
    message: str
    deleted_count: int


class LaunchGameResponse(BaseModel):
    success: bool
    message: str


class DatabaseStatsResponse(BaseModel):
    catalog_mods_count: int
    installed_mods_count: int
    db_path: str


class DatabasePurgeResponse(BaseModel):
    success: bool
    deleted_count: int
    message: str
