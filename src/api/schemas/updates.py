from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class UpdateModItem(BaseModel):
    """Classe UpdateModItem : assure la gestion et l'orchestration de Updatemoditem."""

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
    """Classe UpdatesListResponse : assure la gestion et l'orchestration de Updateslistresponse."""

    count: int
    total_installed: int = 0
    items: List[UpdateModItem]


class UpdateBatchRequest(BaseModel):
    """Classe UpdateBatchRequest : assure la gestion et l'orchestration de Updatebatchrequest."""

    installed_ids: List[int]


class UpdateModResponse(BaseModel):
    """Classe UpdateModResponse : assure la gestion et l'orchestration de Updatemodresponse."""

    success: bool
    message: str


class UpdateAllResponse(BaseModel):
    """Classe UpdateAllResponse : assure la gestion et l'orchestration de Updateallresponse."""

    success: bool
    updated_count: int
    total_count: int
    message: str
    details: List[Dict[str, Any]] = []
