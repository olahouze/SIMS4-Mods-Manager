import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from src.api.models import LogsResponse, ClearLogsResponse, OpenLogsFolderResponse
from src.utils.logger import qt_log_handler

router = APIRouter(prefix="/logs", tags=["Logs & Diagnostics"])


@router.get("", response_model=LogsResponse)
def get_logs(
    level: Optional[str] = Query(None, description="INFO, WARNING, ERROR, DEBUG"),
    search: Optional[str] = Query(None, description="Keyword search in logs"),
    limit: int = Query(200, ge=1, le=2000),
):
    """Returns application logs with optional level and keyword filtering."""
    raw_history = list(qt_log_handler.history)

    filtered = []
    for line in raw_history:
        if search and search.lower() not in line.lower():
            continue
        if level and level.upper() != "ALL":
            if f"[{level.upper()}]" not in line:
                continue
        filtered.append(line)

    sliced = filtered[-limit:]
    return LogsResponse(total=len(sliced), items=sliced)


@router.delete("", response_model=ClearLogsResponse)
def clear_logs():
    """Clears the in-memory log buffer."""
    qt_log_handler.history.clear()
    return ClearLogsResponse(success=True, message="Historique des logs effacé avec succès.")


@router.post("/open-folder", response_model=OpenLogsFolderResponse)
def open_logs_folder():
    """Opens the local logs folder in Windows Explorer."""
    log_dir = Path.home() / ".sims4_mod_manager" / "logs"
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)

    try:
        os.startfile(str(log_dir))
        return OpenLogsFolderResponse(success=True, message=f"Dossier des logs ouvert: {log_dir}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Impossible d'ouvrir le dossier des logs: {e}")
