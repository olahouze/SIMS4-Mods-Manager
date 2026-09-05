from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# --- Accounts ---
class AccountStatusItem(BaseModel):
    provider_name: str
    is_configured: bool
    is_ready: bool
    is_member: bool
    user_display_name: str
    cookies_count: int
    last_verified: Optional[datetime] = None


class AccountListResponse(BaseModel):
    accounts: List[AccountStatusItem]


class AccountActionResponse(BaseModel):
    success: bool
    message: str


class AccountLoginRequest(BaseModel):
    timeout_seconds: int = 300


class AccountLoginResponse(BaseModel):
    success: bool
    message: str
    cookies_count: int = 0


# --- Catalog ---
class CatalogModItem(BaseModel):
    id: int
    source: str
    remote_id: str
    title: str
    author: str
    category: str
    page_url: str
    thumbnail_url: str
    published_date: Optional[datetime] = None
    updated_date: Optional[datetime] = None
    patreon_status: str
    patreon_tier: str
    tags: List[str] = []
    is_installed: bool = False
    has_update: bool = False
    requirements_text: Optional[str] = None
    requirements_status: str = "NONE"
    dependencies: List["DependencyItem"] = []


class DependencyItem(BaseModel):
    source: str = "loverslab"
    remote_id: str = ""
    title: str
    url: str = ""
    is_installed: bool = False
    status: str = "DETECTED_NOT_INSTALLED"  # "INSTALLED", "DETECTED_NOT_INSTALLED", "NOT_DETECTED_SCANNING", "NOT_DETECTED_FINISHED"


class DependenciesCheckResponse(BaseModel):
    mod_title: str
    requirements_status: str
    requirements_text: Optional[str] = None
    can_install: bool = True
    is_partial: bool = False
    unfound_dependencies: List[DependencyItem] = []
    blocking_reason: Optional[str] = None
    already_installed_dependencies: List[DependencyItem] = []
    missing_dependencies: List[DependencyItem] = []


class CatalogListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[CatalogModItem]


class CatalogSyncRequest(BaseModel):
    max_pages: int = Field(default=0, ge=0, le=1000, description="0 = toutes les pages disponibles")


class SubCategoryProgress(BaseModel):
    id: str
    name: str
    pages_completed: int = 0
    total_pages: int = 0
    mods_count: int = 0
    status: str = "PENDING"  # "PENDING", "IN_PROGRESS", "COMPLETED", "ERROR"


class CatalogSyncStatusResponse(BaseModel):
    is_running: bool
    progress_percent: int
    message: str
    total_scraped: int
    pages_completed: int = 0
    total_pages: int = 0
    current_category: Optional[str] = None
    has_error: bool = False
    error_message: Optional[str] = None
    page1_ready: bool = False
    last_completed_at: Optional[str] = None
    categories_progress: List[SubCategoryProgress] = []
    providers_status: Dict[str, str] = {}


class CatalogInstallRequest(BaseModel):
    catalog_mod_id: Optional[int] = None
    source: Optional[str] = "loverslab"
    remote_id: Optional[str] = None
    page_url: Optional[str] = None
    title: Optional[str] = None
    updated_date: Optional[datetime] = None
    install_dependencies: bool = True
    allow_partial: bool = True


class CatalogInstallResponse(BaseModel):
    success: bool
    message: str
    installed_dependencies: List[str] = []


class ModDetailsResponse(BaseModel):
    id: Optional[int] = None
    source: str
    remote_id: str
    title: str
    author: Optional[str] = None
    description: str = ""
    page_url: str
    thumbnail_url: Optional[str] = None
    tags: List[str] = []
    updated_date: Optional[str] = None
    patreon_status: str = "NONE"
    patreon_tier: str = ""
    requirements_text: Optional[str] = None
    requirements_status: str = "NONE"
    dependencies: List[DependencyItem] = []
    screenshots: List[str] = []


# --- Installed Mods ---
class InstalledModItem(BaseModel):
    id: int
    catalog_mod_id: Optional[int] = None
    source: str
    remote_id: str
    title: str
    author: str = ""
    folder_name: str
    thumbnail_url: str = ""
    page_url: str = ""
    requirements_text: Optional[str] = None
    requirements_status: str = "NONE"
    dependencies: List[DependencyItem] = []
    screenshots: List[str] = []
    is_enabled: bool
    installed_date: Optional[datetime] = None
    version_date: Optional[datetime] = None
    version_str: str = ""
    files_count: int = 0
    files_list: List[str] = []
    backup_path: Optional[str] = None
    has_update: bool = False


class InstalledListResponse(BaseModel):
    total: int
    enabled_count: int
    disabled_count: int
    items: List[InstalledModItem]


class InstalledToggleRequest(BaseModel):
    enabled: Optional[bool] = None


class InstalledToggleResponse(BaseModel):
    success: bool
    message: str
    is_enabled: bool


class InstalledUninstallResponse(BaseModel):
    success: bool
    message: str


class InstalledScanResponse(BaseModel):
    success: bool
    message: str
    count: int
    found: List[Dict[str, Any]] = []


class InstalledOpenFolderRequest(BaseModel):
    folder_name: Optional[str] = None


class InstalledOpenFolderResponse(BaseModel):
    success: bool
    message: str


# --- Updates ---
class UpdateModItem(BaseModel):
    installed_id: int
    title: str
    source: str
    folder_name: str
    current_version: str = "Inconnue"
    new_version: str = "Inconnue"
    has_update: bool = False
    current_version_date: Optional[str] = None
    new_version_date: Optional[str] = None
    catalog_mod_id: Optional[int] = None
    remote_id: Optional[str] = None
    page_url: Optional[str] = None


class UpdatesListResponse(BaseModel):
    count: int
    total_installed: int = 0
    items: List[UpdateModItem]


class UpdateBatchRequest(BaseModel):
    installed_ids: List[int]


class UpdateModResponse(BaseModel):
    success: bool
    message: str


class UpdateAllResponse(BaseModel):
    success: bool
    updated_count: int
    total_count: int
    message: str
    details: List[Dict[str, Any]] = []


# --- Settings ---
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


# --- Logs ---
class LogsResponse(BaseModel):
    total: int
    items: List[str]


class ClearLogsResponse(BaseModel):
    success: bool
    message: str


class OpenLogsFolderResponse(BaseModel):
    success: bool
    message: str


# --- System & Health ---
class HealthResponse(BaseModel):
    status: str
    version: str
    game_detected: bool
    mods_dir_detected: bool
    mods_dir: Optional[str] = None
    browser_engine_ready: bool
    database_ok: bool
