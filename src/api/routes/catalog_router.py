import re
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session, defer

from src.api.schemas.catalog import (
    CatalogListResponse,
    CatalogModItem,
    CatalogSyncRequest,
    CatalogSyncStatusResponse,
    ModDetailsResponse,
)
from src.database.models import CatalogMod, InstalledMod
from src.api.deps import get_db
from src.providers import ProviderRegistry
from src.services.catalog_sync_service import (
    SyncTracker,
    run_catalog_sync,
)
from src.services.dependency_resolver import resolve_mod_dependencies
from src.services.mod_installer_service import perform_mod_install
from src.services.mod_update_service import check_has_update
from src.utils.logger import logger
from src.utils.mod_type_classifier import ModTypeClassifier


from src.api.routes.catalog_reports_router import reports_router
from src.api.routes.catalog_install_router import install_router

_run_catalog_sync = run_catalog_sync
_perform_install = perform_mod_install

router = APIRouter(prefix="/catalog", tags=["Catalog"])
router.include_router(reports_router)
router.include_router(install_router)


@router.get("", response_model=CatalogListResponse)
def get_catalog(
    search: Optional[str] = None,
    source: Optional[str] = Query(None, description="loverslab, patreon, all"),
    access: Optional[str] = Query(None, description="public, unlocked, locked, all"),
    status: Optional[str] = Query(None, description="all, installed, not_installed, updates_available"),
    mod_type: Optional[str] = Query(None, description="animation, clothing, hair, body_skin, etc."),
    sort: Optional[str] = Query("recent", description="recent, az"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
):
    """Returns catalog mods with filtering, search, status, and pagination using SQL-level filtering."""
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

    if mod_type:
        type_filter = ModTypeClassifier.get_sql_filter(mod_type, CatalogMod)
        if type_filter is not None:
            query = query.filter(type_filter)

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
    paginated_mods = (
        query.options(defer(CatalogMod.description), defer(CatalogMod.requirements_text))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    page_remote_ids = [m.remote_id for m in paginated_mods if m.remote_id]
    page_cat_ids = [m.id for m in paginated_mods if m.id]
    page_titles = [m.title for m in paginated_mods if m.title]

    conditions = []
    if page_remote_ids:
        conditions.append(InstalledMod.remote_id.in_(page_remote_ids))
    if page_cat_ids:
        conditions.append(InstalledMod.catalog_mod_id.in_(page_cat_ids))
    if page_titles:
        conditions.append(InstalledMod.title.in_(page_titles))

    relevant_installed = session.query(InstalledMod).filter(or_(*conditions)).all() if conditions else []
    installed_by_remote = {(im.source, im.remote_id): im for im in relevant_installed if im.remote_id}
    installed_by_title = {im.title.lower(): im for im in relevant_installed if im.title}
    installed_by_id = {
        im.catalog_mod_id: im for im in relevant_installed if im.catalog_mod_id and not im.remote_id
    }

    # Pre-collect all requirement remote_ids for batch lookup (eliminates N+1 queries)
    needed_remote_ids = set()
    for m in paginated_mods:
        for req in m.get_requirements_mods_list():
            rid = str(req.get("remote_id") or "")
            if rid:
                needed_remote_ids.add(rid)

    catalog_remote_ids = set()
    if needed_remote_ids:
        found_rows = (
            session.query(CatalogMod.source, CatalogMod.remote_id)
            .filter(CatalogMod.remote_id.in_(list(needed_remote_ids)))
            .all()
        )
        catalog_remote_ids = {(row[0], str(row[1])) for row in found_rows}

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
            catalog_remote_ids=catalog_remote_ids,
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


@router.post("/sync/pause", response_model=CatalogSyncStatusResponse)
def pause_sync(provider: Optional[str] = Query(None, description="Nom du provider (ex: loverslab)")):
    """Pauses the current catalog synchronization."""
    SyncTracker.pause(provider=provider)
    return SyncTracker.to_response()


@router.post("/sync/resume", response_model=CatalogSyncStatusResponse)
def resume_sync(provider: Optional[str] = Query(None, description="Nom du provider (ex: loverslab)")):
    """Resumes the paused catalog synchronization."""
    SyncTracker.resume(provider=provider)
    return SyncTracker.to_response()


@router.post("/sync/stop", response_model=CatalogSyncStatusResponse)
def stop_sync(provider: Optional[str] = Query(None, description="Nom du provider (ex: loverslab)")):
    """Stops the current catalog synchronization."""
    SyncTracker.stop(provider=provider)
    return SyncTracker.to_response()


@router.get("/{mod_id:int}/details", response_model=ModDetailsResponse)
@router.get("/{mod_id:int}", response_model=ModDetailsResponse)
def get_catalog_mod_details(mod_id: int, force_refresh: bool = False, session: Session = Depends(get_db)):
    """Returns full details for a catalog mod by ID."""
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
        or (m.requirements_text and not m.get_requirements_mods_list())
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
