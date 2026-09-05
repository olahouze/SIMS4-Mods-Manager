from typing import List
from pydantic import BaseModel


class LogsResponse(BaseModel):
    total: int
    items: List[str]


class ClearLogsResponse(BaseModel):
    success: bool
    message: str


class OpenLogsFolderResponse(BaseModel):
    success: bool
    message: str
