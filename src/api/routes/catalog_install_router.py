"""
Endpoints for catalog mod installation, streaming progress, dependencies verification, thumbnails, and maintenance.
"""
import json
import queue
import threading
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from src.api.schemas.catalog import (
    CatalogInstallRequest,
    CatalogInstallResponse,
    DependenciesCheckResponse,
)
from src.core.config import AppConfig
from src.core.session_manager import SessionManager
from src.database.models import CatalogMod
from src.database.manager import DatabaseManager
from src.api.deps import get_db
from src.services.catalog_sync_service import check_catalog_dependencies
from src.services.mod_installer_service import perform_mod_install
from src.utils.logger import logger

install_router = APIRouter(tags=["Catalog Installation"])


@install_router.get("/thumbnail")
def get_thumbnail(source: str, remote_id: str, url: str):
    """Fetches and caches thumbnail image for catalog mod, returning the file."""
    cache_dir = AppConfig.get_thumbnails_cache_dir()
    dest_path = cache_dir / f"thumb_{source}_{remote_id}.jpg"

    if not dest_path.exists() or dest_path.stat().st_size < 100:
        session = SessionManager.get_http_session(source)
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code == 200 and len(resp.content) > 100:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_path, "wb") as f:
                    f.write(resp.content)
            else:
                raise HTTPException(status_code=404, detail="Image introuvable.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Erreur téléchargement image: {e}") from e

    media_type = "image/jpeg"
    try:
        with open(dest_path, "rb") as f:
            header = f.read(12)
        if header.startswith(b"\x89PNG"):
            media_type = "image/png"
        elif header.startswith(b"RIFF") and b"WEBP" in header:
            media_type = "image/webp"
        elif header.startswith(b"GIF8"):
            media_type = "image/gif"
    except (OSError, IOError) as e:
        logger.debug(f"Could not read image header for {dest_path}: {e}")

    return FileResponse(dest_path, media_type=media_type)


@install_router.post("/purge")
def purge_catalog_endpoint():
    """Purges all catalog mods to restart from a clean catalog."""
    db = DatabaseManager.get_instance()
    deleted = db.purge_catalog()
    return {"success": True, "deleted": deleted, "message": f"{deleted} mod(s) supprimé(s) du catalogue."}


@install_router.post("/check-dependencies", response_model=DependenciesCheckResponse)
def check_dependencies(payload: CatalogInstallRequest, session: Session = Depends(get_db)):
    """Analyzes the dependency tree for a mod before installation."""
    cat_mod = None
    if payload.catalog_mod_id:
        cat_mod = session.query(CatalogMod).filter_by(id=payload.catalog_mod_id).first()
    elif payload.source and payload.remote_id:
        cat_mod = session.query(CatalogMod).filter_by(source=payload.source, remote_id=payload.remote_id).first()

    page_url = cat_mod.page_url if cat_mod else payload.page_url
    source = cat_mod.source if cat_mod else (payload.source or "loverslab")
    mod_title = cat_mod.title if cat_mod else (payload.title or "Mod")

    return check_catalog_dependencies(
        mod_title=mod_title,
        page_url=page_url,
        source=source,
        cat_mod=cat_mod,
    )


@install_router.post("/install", response_model=CatalogInstallResponse)
def install_mod(payload: CatalogInstallRequest):
    """Downloads and installs a mod given its catalog id or source and remote_id/page_url."""
    from src.api.routes import catalog_router
    perform_fn = getattr(catalog_router, "_perform_install", perform_mod_install)
    res = perform_fn(payload)
    if not res.success and "introuvable" in res.message:
        raise HTTPException(status_code=400, detail=res.message)
    return res


@install_router.post("/install-stream")
def install_mod_stream(payload: CatalogInstallRequest):
    """Downloads and installs a mod while streaming real-time progress events as newline-delimited JSON."""
    from src.api.routes import catalog_router
    perform_fn = getattr(catalog_router, "_perform_install", perform_mod_install)
    q = queue.Queue()

    def progress_cb(pct: int, status: str, details: str = ""):
        q.put({"type": "progress", "percent": pct, "status": status, "details": details})

    def run_worker():
        try:
            res = perform_fn(payload, progress_callback=progress_cb)
            q.put({"type": "finished", "success": res.success, "message": res.message})
        except Exception as e:
            q.put({"type": "finished", "success": False, "message": str(e)})
        finally:
            q.put(None)

    threading.Thread(target=run_worker, daemon=True).start()

    def event_generator():
        while True:
            item = q.get()
            if item is None:
                break
            yield json.dumps(item) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")
