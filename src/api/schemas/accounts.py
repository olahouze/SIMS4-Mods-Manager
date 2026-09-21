from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class AccountStatusItem(BaseModel):
    """Classe AccountStatusItem : assure la gestion et l'orchestration de Accountstatusitem."""

    provider_name: str
    is_configured: bool
    is_ready: bool
    is_member: bool
    user_display_name: str
    cookies_count: int
    last_verified: Optional[datetime] = None


class AccountListResponse(BaseModel):
    """Classe AccountListResponse : assure la gestion et l'orchestration de Accountlistresponse."""

    accounts: List[AccountStatusItem]


class AccountActionResponse(BaseModel):
    """Classe AccountActionResponse : assure la gestion et l'orchestration de Accountactionresponse."""

    success: bool
    message: str


class AccountLoginRequest(BaseModel):
    """Classe AccountLoginRequest : assure la gestion et l'orchestration de Accountloginrequest."""

    timeout_seconds: int = 300


class AccountLoginResponse(BaseModel):
    """Classe AccountLoginResponse : assure la gestion et l'orchestration de Accountloginresponse."""

    success: bool
    message: str
    cookies_count: int = 0
