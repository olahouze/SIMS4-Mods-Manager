from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


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
    dependencies: List[DependencyItem] = []


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
