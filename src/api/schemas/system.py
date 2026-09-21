from typing import Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Classe HealthResponse : assure la gestion et l'orchestration de Healthresponse."""

    status: str
    version: str
    game_detected: bool
    mods_dir_detected: bool
    mods_dir: Optional[str] = None
    browser_engine_ready: bool
    database_ok: bool
