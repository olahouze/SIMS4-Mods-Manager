from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from src.api.schemas.catalog import DependencyItem


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


class ModDependentItem(BaseModel):
    id: int
    title: str
    folder_name: str


class ModDependentsResponse(BaseModel):
    mod_id: int
    mod_title: str
    has_dependents: bool
    count: int
    dependents: List[ModDependentItem]
