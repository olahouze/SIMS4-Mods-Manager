from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


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
