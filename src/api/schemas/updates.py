from typing import Optional, List, Dict, Any
from pydantic import BaseModel


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
