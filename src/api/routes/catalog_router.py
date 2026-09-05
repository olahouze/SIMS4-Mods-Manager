import json
import queue
import re
import threading
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse

from src.api.schemas.catalog import (
    CatalogListResponse,
    CatalogModItem,
    CatalogSyncRequest,
    CatalogSyncStatusResponse,
    CatalogInstallRequest,
    CatalogInstallResponse,
    ModDetailsResponse,
    DependenciesCheckResponse,
)
from src.core.config import AppConfig
from src.database.models import CatalogMod, InstalledMod
from src.database.manager import DatabaseManager
from src.core.session_manager import SessionManager
from src.providers import ProviderRegistry
from src.services.catalog_sync_service import (
    SyncTracker,
    run_catalog_sync,
    check_catalog_dependencies,
)
from src.services.dependency_resolver import resolve_mod_dependencies
from src.services.mod_installer_service import perform_mod_install
from src.services.mod_update_service import check_has_update
from src.utils.logger import logger

_run_catalog_sync = run_catalog_sync
_perform_install = perform_mod_install

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get("", response_model=CatalogListResponse)
def get_catalog(
    search: Optional[str] = None,
    source: Optional[str] = Query(None, description="loverslab, patreon, all"),
    access: Optional[str] = Query(None, description="public, unlocked, locked, all"),
    status: Optional[str] = Query(None, description="all, installed, not_installed, updates_available"),
    sort: Optional[str] = Query("recent", description="recent, az"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """Returns catalog mods with filtering, search, status, and pagination using SQL-level filtering."""
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        query = session.query(CatalogMod)

        if search:
            s_clean = search.strip()
            query = query.filter(
                (CatalogMod.title.ilike(f"%{s_clean}%"))
                | (CatalogMod.author.ilike(f"%{s_clean}%"))
                | (CatalogMod.tags.ilike(f"%{s_clean}%"))
            )

        if source and source.lower() != "all":
            query = query.filter(CatalogMod.source == source.lower())

        # Support access filters passed in either access or status param
        if status and status.lower() in [
            "direct",
            "site_direct",
            "needs_account",
            "account",
            "connexion",
            "needs_sub",
            "subscription",
            "abonnement",
            "locked",
        ]:
            if not access or access.lower() == "all":
                access = status
                status = None

        if access and access.lower() != "all":
            acc = access.lower()
            if acc in ["direct", "site_direct"]:
                query = query.filter(
                    CatalogMod.source != "patreon",
                    (CatalogMod.patreon_status == "NONE")
                    | (CatalogMod.patreon_status.is_(None))
                    | (CatalogMod.patreon_status == ""),
                    ~CatalogMod.tags.ilike("%Patreon%"),
                )
            elif acc in ["needs_account", "account", "connexion"]:
                query = query.filter(
                    (CatalogMod.source == "patreon")
                    | (CatalogMod.patreon_status == "PUBLIC")
                    | (CatalogMod.tags.ilike("%Patreon%"))
                ).filter(
                    CatalogMod.patreon_status != "LOCKED",
                    CatalogMod.patreon_status != "UNLOCKED",
                )
            elif acc in ["needs_sub", "subscription", "abonnement", "locked", "verrouillé"]:
                query = query.filter(
                    (CatalogMod.patreon_status == "LOCKED")
                    | (
                        (CatalogMod.source == "patreon")
                        & (CatalogMod.patreon_tier != "")
                        & (CatalogMod.patreon_status != "UNLOCKED")
                    )
                )
            elif acc in ["unlocked", "débloqué"]:
                query = query.filter(CatalogMod.patreon_status == "UNLOCKED")
            elif acc in ["public", "gratuit"]:
                query = query.filter(CatalogMod.patreon_status.in_(["PUBLIC", "NONE"]))

        # SQL-level status filtering
        if status and status.lower() not in ["all", ""]:
            st = status.lower()
            installed_match = (
                (InstalledMod.source == CatalogMod.source) & (InstalledMod.remote_id == CatalogMod.remote_id)
            ) | (
                (InstalledMod.catalog_mod_id == CatalogMod.id)
                & ((InstalledMod.remote_id.is_(None)) | (InstalledMod.remote_id == ""))
            )

            if st == "installed":
                query = query.filter(session.query(InstalledMod.id).filter(installed_match).exists())
            elif st == "not_installed":
                query = query.filter(~session.query(InstalledMod.id).filter(installed_match).exists())
            elif st == "updates_available":
                has_newer = (CatalogMod.updated_date.isnot(None)) & (
                    InstalledMod.version_date.is_(None)
                    | (CatalogMod.updated_date > InstalledMod.version_date)
                    | (
                        CatalogMod.version_str.isnot(None)
                        & InstalledMod.version_str.isnot(None)
                        & (CatalogMod.version_str != InstalledMod.version_str)
                    )
                )
                query = query.filter(session.query(InstalledMod.id).filter(installed_match, has_newer).exists())

        if sort == "az":
            query = query.order_by(CatalogMod.title.asc())
        else:
            query = query.order_by(CatalogMod.updated_date.desc().nullslast())

        total = query.count()
        paginated_mods = query.offset((page - 1) * limit).limit(limit).all()

        all_installed = session.query(InstalledMod).all()
        installed_by_remote = {(im.source, im.remote_id): im for im in all_installed if im.remote_id}
        installed_by_title = {im.title.lower(): im for im in all_installed if im.title}
        installed_by_id = {
            im.catalog_mod_id: im for im in all_installed if im.catalog_mod_id and not im.remote_id
        }

        paginated_items = []
        for m in paginated_mods:
            inst = installed_by_remote.get((m.source, m.remote_id)) or installed_by_id.get(m.id)
            is_installed = inst is not None
            has_update = check_has_update(inst, m) if is_installed else False

            dep_items = resolve_mod_dependencies(
                m.get_requirements_mods_list(),
                session,
                installed_by_remote,
                installed_by_title,
                is_syncing=SyncTracker.is_running,
            )

            paginated_items.append(
                CatalogModItem(
                    id=m.id,
                    source=m.source,
                    remote_id=m.remote_id,
                    title=m.title,
                    author=m.author or "",
                    category=m.category or "",
                    page_url=m.page_url,
                    thumbnail_url=m.thumbnail_url or "",
                    published_date=m.published_date,
                    updated_date=m.updated_date,
                    patreon_status=m.patreon_status or "NONE",
                    patreon_tier=m.patreon_tier or "",
                    tags=m.get_tags_list(),
                    is_installed=is_installed,
                    has_update=has_update,
                    requirements_text=m.requirements_text,
                    requirements_status=m.requirements_status or "NONE",
                    dependencies=dep_items,
                )
            )

        return CatalogListResponse(
            total=total,
            page=page,
            limit=limit,
            items=paginated_items,
        )


@router.post("/sync", response_model=CatalogSyncStatusResponse)
def start_sync(payload: CatalogSyncRequest, background_tasks: BackgroundTasks):
    """Triggers multi-source catalog synchronization."""
    if SyncTracker.is_running:
        resp = SyncTracker.to_response()
        resp.message = "Une synchronisation est déjà en cours d'exécution."
        return resp

    providers = ProviderRegistry.list_providers()
    ll_provider = next((p for p in providers if getattr(p, "provider_name", "") == "loverslab"), None)
    categories = getattr(ll_provider, "CATEGORIES", [])
    initial_pages = (
        sum(c.get("default_pages", 1) for c in categories)
        if payload.max_pages <= 0
        else (len(categories) * payload.max_pages)
    )
    page_msg = (
        "toutes les pages détectées" if payload.max_pages <= 0 else f"{payload.max_pages} pages par source"
    )
    SyncTracker.start(initial_pages, categories_list=categories)
    SyncTracker.message = f"Synchronisation démarrée ({page_msg})."
    background_tasks.add_task(_run_catalog_sync, payload.max_pages)
    return SyncTracker.to_response()


@router.get("/sync/status", response_model=CatalogSyncStatusResponse)
def get_sync_status():
    """Returns current catalog scraping progress status."""
    return SyncTracker.to_response()


@router.get("/thumbnail")
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
    except Exception:
        pass

    return FileResponse(dest_path, media_type=media_type)


@router.post("/purge")
def purge_catalog_endpoint():
    """Purges all catalog mods to restart from a clean catalog."""
    db = DatabaseManager.get_instance()
    deleted = db.purge_catalog()
    return {"success": True, "deleted": deleted, "message": f"{deleted} mod(s) supprimé(s) du catalogue."}


@router.get("/{mod_id:int}/details", response_model=ModDetailsResponse)
@router.get("/{mod_id:int}", response_model=ModDetailsResponse)
def get_catalog_mod_details(mod_id: int, force_refresh: bool = False):
    """Returns full details for a catalog mod by ID."""
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        m = session.query(CatalogMod).filter_by(id=mod_id).first()
        if not m:
            raise HTTPException(status_code=404, detail="Mod introuvable dans le catalogue.")

        desc = m.description
        is_legacy = (
            desc
            and desc.strip()
            and (
                len(desc.strip()) < 50
                or "<div" not in desc
                or "background-color:#0d0d0d" in desc
                or "background-color:" in desc
            )
        )
        if (
            force_refresh
            or not desc
            or is_legacy
            or not m.requirements_status
            or m.requirements_status == "NONE"
        ) and m.page_url:
            try:
                provider = ProviderRegistry.get_provider(m.source)
                if provider:
                    details = provider.get_mod_details(m.page_url)
                    fetched_desc = details.get("description", "")
                    if fetched_desc:
                        m.description = fetched_desc
                        desc = fetched_desc
                    if details.get("requirements_text") is not None or details.get("requirements_status"):
                        m.requirements_text = details.get("requirements_text")
                        m.requirements_status = details.get("requirements_status", "NONE")
                        m.set_requirements_mods_list(details.get("requirements_mods", []))
                    session.commit()
            except Exception as e:
                logger.debug(f"Erreur extraction détails/requirements pour {m.title}: {e}")

        all_inst = session.query(InstalledMod).all()
        installed_by_remote = {(im.source, im.remote_id): im for im in all_inst if im.remote_id}
        installed_by_title = {im.title.lower(): im for im in all_inst if im.title}
        dep_items = resolve_mod_dependencies(
            m.get_requirements_mods_list(),
            session,
            installed_by_remote,
            installed_by_title,
            is_syncing=SyncTracker.is_running,
        )

        screenshots = details.get("screenshots", []) if "details" in locals() else []
        if not screenshots and desc:
            imgs_in_desc = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
            screenshots = [
                u
                for u in imgs_in_desc
                if any(k in u.lower() for k in ["screenshot", "upload", "gallery", "image"])
                and not any(k in u.lower() for k in ["reaction", "icon", "theme", "emoticon"])
            ]

        return ModDetailsResponse(
            id=m.id,
            source=m.source,
            remote_id=m.remote_id,
            title=m.title,
            author=m.author or "Inconnu",
            description=desc or "Aucune description détaillée disponible pour ce mod.",
            page_url=m.page_url,
            thumbnail_url=m.thumbnail_url or "",
            tags=m.get_tags_list(),
            updated_date=m.updated_date.strftime("%d/%m/%Y") if m.updated_date else None,
            patreon_status=m.patreon_status or "NONE",
            patreon_tier=m.patreon_tier or "",
            requirements_text=m.requirements_text,
            requirements_status=m.requirements_status or "NONE",
            dependencies=dep_items,
            screenshots=screenshots,
        )


@router.post("/check-dependencies", response_model=DependenciesCheckResponse)
def check_dependencies(payload: CatalogInstallRequest):
    """Analyzes the dependency tree for a mod before installation."""
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
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


@router.post("/install", response_model=CatalogInstallResponse)
def install_mod(payload: CatalogInstallRequest):
    """Downloads and installs a mod given its catalog id or source and remote_id/page_url."""
    res = perform_mod_install(payload)
    if not res.success and "introuvable" in res.message:
        raise HTTPException(status_code=400, detail=res.message)
    return res


@router.post("/install-stream")
def install_mod_stream(payload: CatalogInstallRequest):
    """Downloads and installs a mod while streaming real-time progress events as newline-delimited JSON."""
    q = queue.Queue()

    def progress_cb(pct: int, status: str, details: str = ""):
        q.put({"type": "progress", "percent": pct, "status": status, "details": details})

    def run_worker():
        try:
            res = _perform_install(payload, progress_callback=progress_cb)
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
