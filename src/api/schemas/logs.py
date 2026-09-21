from typing import List
from pydantic import BaseModel


class LogsResponse(BaseModel):
    """Classe LogsResponse : assure la gestion et l'orchestration de Logsresponse."""

    total: int
    items: List[str]


class ClearLogsResponse(BaseModel):
    """Classe ClearLogsResponse : assure la gestion et l'orchestration de Clearlogsresponse."""

    success: bool
    message: str


class OpenLogsFolderResponse(BaseModel):
    """Classe OpenLogsFolderResponse : assure la gestion et l'orchestration de Openlogsfolderresponse."""

    success: bool
    message: str
