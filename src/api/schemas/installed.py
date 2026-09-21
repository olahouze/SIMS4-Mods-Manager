from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from src.api.schemas.catalog import DependencyItem


class InstalledModItem(BaseModel):
    """Classe InstalledModItem : assure la gestion et l'orchestration de Installedmoditem."""

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
    """Classe InstalledListResponse : assure la gestion et l'orchestration de Installedlistresponse."""

    total: int
    enabled_count: int
    disabled_count: int
    items: List[InstalledModItem]


class InstalledToggleRequest(BaseModel):
    """Classe InstalledToggleRequest : assure la gestion et l'orchestration de Installedtogglerequest."""

    enabled: Optional[bool] = None


class InstalledToggleResponse(BaseModel):
    """Classe InstalledToggleResponse : assure la gestion et l'orchestration de Installedtoggleresponse."""

    success: bool
    message: str
    is_enabled: bool


class InstalledUninstallResponse(BaseModel):
    """Classe InstalledUninstallResponse : assure la gestion et l'orchestration de Installeduninstallresponse."""

    success: bool
    message: str


class InstalledScanResponse(BaseModel):
    """Classe InstalledScanResponse : assure la gestion et l'orchestration de Installedscanresponse."""

    success: bool
    message: str
    count: int
    found: List[Dict[str, Any]] = []


class InstalledOpenFolderRequest(BaseModel):
    """Classe InstalledOpenFolderRequest : assure la gestion et l'orchestration de Installedopenfolderrequest."""

    folder_name: Optional[str] = None


class InstalledOpenFolderResponse(BaseModel):
    """Classe InstalledOpenFolderResponse : assure la gestion et l'orchestration de Installedopenfolderresponse."""

    success: bool
    message: str


class ModDependentItem(BaseModel):
    """Classe ModDependentItem : assure la gestion et l'orchestration de Moddependentitem."""

    id: int
    title: str
    folder_name: str


class ModDependentsResponse(BaseModel):
    """Classe ModDependentsResponse : assure la gestion et l'orchestration de Moddependentsresponse."""

    mod_id: int
    mod_title: str
    has_dependents: bool
    count: int
    dependents: List[ModDependentItem]
