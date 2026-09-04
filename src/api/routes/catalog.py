import json
import queue
import re
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse

from src.api.models import (
    CatalogListResponse,
    CatalogModItem,
    CatalogSyncRequest,
    CatalogSyncStatusResponse,
    SubCategoryProgress,
    CatalogInstallRequest,
    CatalogInstallResponse,
    ModDetailsResponse,
    DependencyItem,
    DependenciesCheckResponse,
)
from src.core.config import AppConfig
from src.core.database import DatabaseManager, CatalogMod, InstalledMod
from src.core.mod_installer import ModInstaller
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.core.update_checker import check_has_update
from src.providers import ProviderRegistry
from src.providers.loverslab import is_wickedwhims_name, is_nisa_name
from src.utils.logger import logger

router = APIRouter(prefix="/catalog", tags=["Catalog"])


# Global Sync Tracker State (§3.3)
# Global Sync Tracker State (§3.3)
class SyncTracker:
    """Thread-safe tracker for catalog synchronization progress."""

    _lock = threading.Lock()
    is_running: bool = False
    stop_requested: bool = False
    progress_percent: int = 0
    message: str = "Prêt"
    total_scraped: int = 0
    pages_completed: int = 0
    total_pages: int = 0
    current_category: Optional[str] = None
    has_error: bool = False
    error_message: Optional[str] = None
    page1_ready: bool = False
    last_completed_at: Optional[str] = None
    categories: Dict[str, Dict[str, Any]] = {}
    providers_status: Dict[str, str] = {"loverslab": "OK", "patreon": "OK"}

    @classmethod
    def start(cls, max_pages: int, categories_list: Optional[List[Dict[str, Any]]] = None) -> None:
        with cls._lock:
            cls.is_running = True
            cls.stop_requested = False
            cls.progress_percent = 0
            cls.message = "Démarrage de la synchronisation..."
            cls.total_scraped = 0
            cls.pages_completed = 0
            cls.total_pages = max_pages
            cls.current_category = "Initialisation..."
            cls.has_error = False
            cls.error_message = None
            cls.page1_ready = False
            cls.providers_status["loverslab"] = "RUNNING"
            if categories_list:
                cls.categories = {
                    c["id"]: {
                        "id": c["id"],
                        "name": c["name"],
                        "pages_completed": 0,
                        "total_pages": c.get("default_pages", 1),
                        "mods_count": 0,
                        "status": "PENDING",
                    }
                    for c in categories_list
                }

    @classmethod
    def update_progress(cls, percent: int, message: str, current_category: Optional[str] = None) -> None:
        with cls._lock:
            cls.progress_percent = max(0, min(100, percent))
            cls.message = message
            if current_category:
                cls.current_category = current_category

    @classmethod
    def record_page(cls, new_count: int, is_first_page: bool = False) -> None:
        with cls._lock:
            cls.pages_completed += 1
            cls.total_scraped += new_count
            if is_first_page:
                cls.page1_ready = True
            if cls.total_pages > 0:
                cls.progress_percent = int((cls.pages_completed / cls.total_pages) * 100)

    @classmethod
    def update_category(
        cls, cat_id: str, pages_completed: int, total_pages: int, mods_count: int, status: str
    ) -> None:
        with cls._lock:
            if cat_id in cls.categories:
                cls.categories[cat_id].update({
                    "pages_completed": pages_completed,
                    "total_pages": total_pages,
                    "mods_count": mods_count,
                    "status": status,
                })
            else:
                cls.categories[cat_id] = {
                    "id": cat_id,
                    "name": cat_id,
                    "pages_completed": pages_completed,
                    "total_pages": total_pages,
                    "mods_count": mods_count,
                    "status": status,
                }

    @classmethod
    def set_error(cls, message: str) -> None:
        with cls._lock:
            cls.has_error = True
            cls.error_message = message
            cls.message = f"Erreur: {message}"
            cls.providers_status["loverslab"] = "ERROR"

    @classmethod
    def finish(cls, total_new: int) -> None:
        with cls._lock:
            cls.progress_percent = 100
            cls.total_scraped = total_new
            cls.message = f"Synchronisation terminée avec succès ({total_new} nouveaux mods indexés)."
            cls.current_category = "Terminé"
            cls.last_completed_at = datetime.now().isoformat()
            cls.is_running = False
            cls.providers_status["loverslab"] = "OK"

    @classmethod
    def stop(cls) -> None:
        with cls._lock:
            cls.is_running = False
            cls.stop_requested = True
            if not cls.has_error:
                cls.providers_status["loverslab"] = "OK"


    @classmethod
    def to_response(cls) -> CatalogSyncStatusResponse:
        with cls._lock:
            db_count = DatabaseManager.get_instance().get_catalog_mods_count()
            cat_items = [
                SubCategoryProgress(
                    id=c["id"],
                    name=c["name"],
                    pages_completed=c["pages_completed"],
                    total_pages=c["total_pages"],
                    mods_count=c["mods_count"],
                    status=c["status"],
                )
                for c in cls.categories.values()
            ]
            return CatalogSyncStatusResponse(
                is_running=cls.is_running,
                progress_percent=cls.progress_percent,
                message=cls.message,
                total_scraped=max(cls.total_scraped, db_count),
                pages_completed=cls.pages_completed,
                total_pages=cls.total_pages,
                current_category=cls.current_category,
                has_error=cls.has_error,
                error_message=cls.error_message,
                page1_ready=cls.page1_ready,
                last_completed_at=cls.last_completed_at,
                categories_progress=cat_items,
                providers_status=dict(cls.providers_status),
            )


ShutdownManager.register_callback(SyncTracker.stop)


def resolve_mod_dependencies(
    raw_deps: List[Dict[str, Any]],
    session,
    installed_by_remote: Dict[Tuple[str, str], Any],
    installed_by_title: Dict[str, Any],
) -> List[DependencyItem]:
    """
    Resolves dependency items against database catalog and installed mods,
    returning DependencyItem objects with one of the 4 exact statuses:
    - INSTALLED
    - DETECTED_NOT_INSTALLED
    - NOT_DETECTED_SCANNING (if sync is currently running)
    - NOT_DETECTED_FINISHED (if sync is finished)
    """
    items = []
    is_syncing = SyncTracker.is_running

    for dep in raw_deps:
        source = dep.get("source", "loverslab")
        r_id = str(dep.get("remote_id") or "")
        title = dep.get("title", "")
        url = dep.get("url", "")

        # 1. If remote_id is missing, search catalog by title or alias
        if not r_id and title:
            if is_wickedwhims_name(title):
                r_id = "3169"
                url = "https://www.loverslab.com/files/file/3169-wickedwhims/"
                title = "WickedWhims"
                source = "loverslab"
            elif is_nisa_name(title):
                r_id = "9443"
                url = "https://www.loverslab.com/files/file/9443-nisas-wicked-perversions/"
                title = "Nisa's Wicked Perversions"
                source = "loverslab"
            else:
                cat_match = (
                    session.query(CatalogMod)
                    .filter((CatalogMod.title.ilike(f"%{title}%")) | (CatalogMod.remote_id == title))
                    .first()
                )
                if cat_match:
                    r_id = cat_match.remote_id
                    url = cat_match.page_url
                    title = cat_match.title
                    source = cat_match.source

        # 2. Check installed status
        is_installed = False
        if r_id and (source, r_id) in installed_by_remote:
            is_installed = True
        elif title.lower() in installed_by_title:
            is_installed = True

        # 3. Determine status among the 4 states
        if is_installed:
            status = "INSTALLED"
        elif r_id:
            exists_in_catalog = (
                session.query(CatalogMod.id).filter_by(source=source, remote_id=r_id).first() is not None
            )
            if exists_in_catalog or r_id == "3169":
                status = "DETECTED_NOT_INSTALLED"
            elif is_syncing:
                status = "NOT_DETECTED_SCANNING"
            else:
                status = "NOT_DETECTED_FINISHED"
        else:
            if is_syncing:
                status = "NOT_DETECTED_SCANNING"
            else:
                status = "NOT_DETECTED_FINISHED"

        items.append(
            DependencyItem(
                source=source,
                remote_id=r_id,
                title=title,
                url=url,
                is_installed=is_installed,
                status=status,
            )
        )
    return items


def _run_catalog_sync(max_pages: int):
    """
    Background task for parallel multi-source scraping by subcategory
    with exponential backoff and thread-safe database commits.
    """
    db = DatabaseManager.get_instance()
    db_lock = threading.Lock()
    providers = ProviderRegistry.list_providers()
    total_new = 0

    ll_provider = None
    for p in providers:
        if getattr(p, "provider_name", "") == "loverslab":
            ll_provider = p
            break

    categories = getattr(ll_provider, "CATEGORIES", [])
    if not categories:
        SyncTracker.finish(0)
        return

    try:
        def _category_worker(cat: Dict[str, Any]) -> int:
            nonlocal total_new
            cat_id = cat["id"]
            cat_name = cat["name"]
            default_p = cat.get("default_pages", 1)
            target_cat_pages = default_p if max_pages <= 0 else min(max_pages, default_p)

            SyncTracker.update_category(cat_id, 0, target_cat_pages, 0, "IN_PROGRESS")
            cat_mods_count = 0

            p = 1
            while p <= target_cat_pages:
                if SyncTracker.stop_requested or ShutdownManager.is_shutting_down():
                    break

                max_retries = 3
                base_delay = 2.0
                mods = []
                scrape_success = False

                for attempt in range(max_retries):
                    if SyncTracker.stop_requested or ShutdownManager.is_shutting_down():
                        break
                    try:
                        mods, detected_pages = ll_provider.scrape_category_page(cat, page=p)
                        scrape_success = True
                        if p == 1 and detected_pages and detected_pages > 0:
                            if max_pages <= 0:
                                target_cat_pages = detected_pages
                            else:
                                target_cat_pages = min(max_pages, detected_pages)
                            with SyncTracker._lock:
                                diff = target_cat_pages - default_p
                                SyncTracker.total_pages = max(1, SyncTracker.total_pages + diff)
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(
                                f"Échec worker LoversLab [{cat_name}] page {p} "
                                f"(tentative {attempt + 1}/{max_retries}). Réessai dans {delay:.1f}s... Erreur: {e}"
                            )
                            time.sleep(delay)
                        else:
                            logger.error(f"Erreur définitive worker LoversLab [{cat_name}] page {p}: {e}", exc_info=True)

                if SyncTracker.stop_requested or ShutdownManager.is_shutting_down():
                    break

                if not scrape_success and not mods:
                    p += 1
                    continue

                new_on_page = 0
                cat_mods_count += len(mods)
                try:
                    with db_lock:
                        with db.get_session() as session:
                            for m_data in mods:
                                existing = (
                                    session.query(CatalogMod)
                                    .filter_by(source=m_data["source"], remote_id=m_data["remote_id"])
                                    .first()
                                )
                                if not existing:
                                    mod_record = CatalogMod(
                                        source=m_data["source"],
                                        remote_id=m_data["remote_id"],
                                        title=m_data["title"],
                                        author=m_data["author"],
                                        category=m_data.get("category", cat_name),
                                        page_url=m_data["page_url"],
                                        thumbnail_url=m_data.get("thumbnail_url", ""),
                                        published_date=m_data.get("published_date"),
                                        updated_date=m_data.get("updated_date"),
                                        patreon_status=m_data.get("patreon_status", "NONE"),
                                        patreon_tier=m_data.get("patreon_tier", ""),
                                    )
                                    mod_record.set_tags_list(m_data.get("tags", []))
                                    session.add(mod_record)
                                    total_new += 1
                                    new_on_page += 1
                                else:
                                    existing.title = m_data["title"]
                                    existing.author = m_data["author"]
                                    existing.thumbnail_url = m_data.get("thumbnail_url", existing.thumbnail_url)
                                    existing.updated_date = m_data.get("updated_date", existing.updated_date)
                                    if m_data.get("patreon_status"):
                                        existing.patreon_status = m_data["patreon_status"]
                                    if m_data.get("patreon_tier"):
                                        existing.patreon_tier = m_data["patreon_tier"]
                                    existing.set_tags_list(m_data.get("tags", []))
                            session.commit()

                    SyncTracker.record_page(new_on_page, is_first_page=(p == 1))
                    SyncTracker.update_category(cat_id, p, target_cat_pages, cat_mods_count, "IN_PROGRESS")
                    SyncTracker.update_progress(
                        SyncTracker.progress_percent,
                        f"Scraping en cours ({SyncTracker.pages_completed}/{SyncTracker.total_pages} pages)",
                        current_category=f"{cat_name} (p. {p}/{target_cat_pages})",
                    )
                except Exception as e:
                    logger.error(f"Erreur enregistrement BDD [{cat_name}] page {p}: {e}", exc_info=True)

                p += 1
                if SyncTracker.stop_requested or ShutdownManager.is_shutting_down():
                    break
                time.sleep(0.3)

            SyncTracker.update_category(cat_id, target_cat_pages, target_cat_pages, cat_mods_count, "COMPLETED")
            return cat_mods_count

        # Execute one worker per category in parallel (up to 8 parallel workers)
        num_workers = min(len(categories), 8)
        logger.info(f"Démarrage du scraping parallèle sur {len(categories)} sous-catégories avec {num_workers} workers.")
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            try:
                list(executor.map(_category_worker, categories))
            except (RuntimeError, KeyboardInterrupt) as e:
                if ShutdownManager.is_shutting_down() or "interpreter shutdown" in str(e).lower():
                    logger.info("Arrêt de la synchronisation suite à la fermeture.")
                    return
                raise

        if not SyncTracker.stop_requested and not ShutdownManager.is_shutting_down():
            SyncTracker.finish(total_new)
    except Exception as e:
        if not ShutdownManager.is_shutting_down() and "interpreter shutdown" not in str(e).lower():
            logger.error(f"Erreur globale de synchronisation: {e}", exc_info=True)
            SyncTracker.set_error(f"Erreur de synchronisation: {e}")
    finally:
        SyncTracker.stop()


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
                # Disponibles directement sur le site (ex: LoversLab direct, sans redirection Patreon)
                query = query.filter(
                    CatalogMod.source != "patreon",
                    (CatalogMod.patreon_status == "NONE")
                    | (CatalogMod.patreon_status.is_(None))
                    | (CatalogMod.patreon_status == ""),
                    ~CatalogMod.tags.ilike("%Patreon%"),
                )
            elif acc in ["needs_account", "account", "connexion"]:
                # Nécessite une connexion à un autre compte (ex: compte Patreon gratuit/connexion requise)
                query = query.filter(
                    (CatalogMod.source == "patreon")
                    | (CatalogMod.patreon_status == "PUBLIC")
                    | (CatalogMod.tags.ilike("%Patreon%"))
                ).filter(
                    CatalogMod.patreon_status != "LOCKED",
                    CatalogMod.patreon_status != "UNLOCKED",
                )
            elif acc in ["needs_sub", "subscription", "abonnement", "locked", "verrouillé"]:
                # Nécessite un abonnement payant (uniquement mods Patreon vérifiés)
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

        # SQL-level status filtering (§1.3)
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

        # Efficient total count and pagination in SQL
        total = query.count()
        paginated_mods = query.offset((page - 1) * limit).limit(limit).all()

        # Build lookup maps for installed mods to decorate the paginated items
        all_installed = session.query(InstalledMod).all()
        installed_by_remote = {(im.source, im.remote_id): im for im in all_installed if im.remote_id}
        installed_by_title = {im.title.lower(): im for im in all_installed if im.title}
        installed_by_id = {
            im.catalog_mod_id: im for im in all_installed if im.catalog_mod_id and not im.remote_id
        }

        paginated_items = []
        for m in paginated_mods:
            # Canonical match by (source, remote_id) first; fallback to FK only for manual/untracked mods
            inst = installed_by_remote.get((m.source, m.remote_id)) or installed_by_id.get(m.id)
            is_installed = inst is not None
            has_update = check_has_update(inst, m) if is_installed else False

            dep_items = resolve_mod_dependencies(
                m.get_requirements_mods_list(),
                session,
                installed_by_remote,
                installed_by_title,
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
    initial_pages = sum(c.get("default_pages", 1) for c in categories) if payload.max_pages <= 0 else (len(categories) * payload.max_pages)
    page_msg = "toutes les pages détectées" if payload.max_pages <= 0 else f"{payload.max_pages} pages par source"
    SyncTracker.start(initial_pages, categories_list=categories)
    SyncTracker.message = f"Synchronisation démarrée ({page_msg})."
    background_tasks.add_task(_run_catalog_sync, payload.max_pages)
    return SyncTracker.to_response()


@router.get("/sync/status", response_model=CatalogSyncStatusResponse)
def get_sync_status():
    """Returns current catalog scraping progress status."""
    return SyncTracker.to_response()


# Static sub-routes defined BEFORE parameterized /{mod_id} to prevent 422 routing collisions
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
    """
    Returns full details for a catalog mod by ID.
    If full description is not in DB or force_refresh is requested,
    scrapes details directly from the source site via provider.
    """
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
        if (force_refresh or not desc or is_legacy or not m.requirements_status or m.requirements_status == "NONE") and m.page_url:
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

        # Check install status of dependencies
        all_inst = session.query(InstalledMod).all()
        installed_by_remote = {(im.source, im.remote_id): im for im in all_inst if im.remote_id}
        installed_by_title = {im.title.lower(): im for im in all_inst if im.title}
        dep_items = resolve_mod_dependencies(
            m.get_requirements_mods_list(),
            session,
            installed_by_remote,
            installed_by_title,
        )

        # Collect screenshots
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
    """
    Analyzes the dependency tree for a mod before installation.
    Detects which dependencies are already installed and which must be fetched,
    or flags the mod if dependencies cannot be resolved on LoversLab or scan is in progress.
    """
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        cat_mod = None
        if payload.catalog_mod_id:
            cat_mod = session.query(CatalogMod).filter_by(id=payload.catalog_mod_id).first()
        elif payload.source and payload.remote_id:
            cat_mod = session.query(CatalogMod).filter_by(source=payload.source, remote_id=payload.remote_id).first()

        # If mod has not been scraped for requirements yet, do so now
        page_url = cat_mod.page_url if cat_mod else payload.page_url
        source = cat_mod.source if cat_mod else (payload.source or "loverslab")
        mod_title = cat_mod.title if cat_mod else (payload.title or "Mod")

        if cat_mod and (not cat_mod.requirements_status or cat_mod.requirements_status == "NONE") and page_url:
            try:
                provider = ProviderRegistry.get_provider(source)
                if provider:
                    details = provider.get_mod_details(page_url)
                    if details.get("requirements_text") is not None or details.get("requirements_status"):
                        cat_mod.requirements_text = details.get("requirements_text")
                        cat_mod.requirements_status = details.get("requirements_status", "NONE")
                        cat_mod.set_requirements_mods_list(details.get("requirements_mods", []))
                        session.commit()
            except Exception as e:
                logger.debug(f"Erreur vérification requirements pour {mod_title}: {e}")

        req_status = cat_mod.requirements_status if cat_mod else "NONE"
        req_text = cat_mod.requirements_text if cat_mod else None
        req_mods = cat_mod.get_requirements_mods_list() if cat_mod else []

        # Check installed dependencies & resolve statuses
        all_inst = session.query(InstalledMod).all()
        installed_by_remote = {(im.source, im.remote_id): im for im in all_inst if im.remote_id}
        installed_by_title = {im.title.lower(): im for im in all_inst if im.title}

        dep_items = resolve_mod_dependencies(
            req_mods,
            session,
            installed_by_remote,
            installed_by_title,
        )

        already_installed = [d for d in dep_items if d.is_installed or d.status == "INSTALLED"]
        missing = [d for d in dep_items if not d.is_installed and d.status != "INSTALLED"]

        not_detected_finished = [d for d in missing if d.status == "NOT_DETECTED_FINISHED"]
        not_detected_scanning = [d for d in missing if d.status == "NOT_DETECTED_SCANNING"]
        unresolved_text_deps = [
            d for d in missing if not d.remote_id and d not in not_detected_finished and d not in not_detected_scanning
        ]

        unfound = list(not_detected_finished) + list(unresolved_text_deps)
        found_missing = [d for d in missing if d not in unfound and d.status != "NOT_DETECTED_SCANNING"]
        is_partial = bool(unfound or req_status == "PENDING_VERIFICATION")

        if is_partial:
            unfound_names = [d.title for d in unfound]
            if not unfound_names and req_text:
                unfound_names = [req_text]
            names_str = ", ".join(f"'{n}'" for n in unfound_names) if unfound_names else "non identifiées"
            warning_msg = (
                f"Ce mod nécessite des dépendances non trouvées sur LoversLab ({names_str}). "
                "L'installation partielle est autorisée, mais le mod risque de ne pas fonctionner correctement sans ces composants."
            )
            return DependenciesCheckResponse(
                mod_title=mod_title,
                requirements_status="PARTIAL" if found_missing else "PENDING_VERIFICATION",
                requirements_text=req_text,
                can_install=True,
                is_partial=True,
                unfound_dependencies=unfound,
                blocking_reason=warning_msg,
                already_installed_dependencies=already_installed,
                missing_dependencies=found_missing,
            )
        elif not_detected_scanning:
            names = ", ".join(f"'{d.title}'" for d in not_detected_scanning)
            return DependenciesCheckResponse(
                mod_title=mod_title,
                requirements_status="WAITING_SCAN",
                requirements_text=req_text,
                can_install=True,
                is_partial=True,
                unfound_dependencies=not_detected_scanning,
                blocking_reason=f"La synchronisation du catalogue est en cours pour : {names}.",
                already_installed_dependencies=already_installed,
                missing_dependencies=found_missing,
            )
        else:
            final_status = "RESOLVED" if req_mods else (req_status or "NONE")
            return DependenciesCheckResponse(
                mod_title=mod_title,
                requirements_status=final_status,
                requirements_text=req_text,
                can_install=True,
                is_partial=False,
                unfound_dependencies=[],
                blocking_reason=None,
                already_installed_dependencies=already_installed,
                missing_dependencies=missing,
            )



def _perform_install(
    payload: CatalogInstallRequest,
    progress_callback=None,
) -> CatalogInstallResponse:
    db = DatabaseManager.get_instance()
    cat_mod = None
    with db.get_session() as session:
        if payload.catalog_mod_id:
            cat_mod = session.query(CatalogMod).filter_by(id=payload.catalog_mod_id).first()
        elif payload.source and payload.remote_id:
            cat_mod = session.query(CatalogMod).filter_by(source=payload.source, remote_id=payload.remote_id).first()

    source = cat_mod.source if cat_mod else (payload.source or "loverslab")
    page_url = cat_mod.page_url if cat_mod else payload.page_url
    mod_title = cat_mod.title if cat_mod else (payload.title or "Mod")
    remote_id = cat_mod.remote_id if cat_mod else (payload.remote_id or "unknown")
    version_date = cat_mod.updated_date if cat_mod else payload.updated_date

    if not page_url:
        return CatalogInstallResponse(success=False, message="Page URL ou identifiant du mod introuvable.")

    # 1. Resolve and cascade installation of missing dependencies
    installed_dependencies = []
    not_detected_deps = []
    if payload.install_dependencies:
        req_mods = cat_mod.get_requirements_mods_list() if cat_mod else []
        req_status = cat_mod.requirements_status if cat_mod else "NONE"

        # If requirements not yet analyzed for this mod, fetch details
        if (not req_mods or req_status in [None, "NONE"]) and page_url:
            try:
                provider = ProviderRegistry.get_provider(source)
                if provider:
                    logger.info(f"[INSTALL-DEP] Analyse préalable des dépendances pour '{mod_title}' ({page_url})...")
                    det = provider.get_mod_details(page_url)
                    req_mods = det.get("requirements_mods", [])
                    req_status = det.get("requirements_status", "NONE")
                    if cat_mod:
                        with db.get_session() as s:
                            cm = s.query(CatalogMod).filter_by(id=cat_mod.id).first()
                            if cm:
                                cm.requirements_text = det.get("requirements_text")
                                cm.requirements_status = req_status
                                cm.set_requirements_mods_list(req_mods)
                                s.commit()
            except Exception as e:
                logger.warning(f"[INSTALL-DEP] Impossible d'analyser les prérequis pour '{mod_title}': {e}")

        # Resolve all dependencies against installed mods and catalog
        with db.get_session() as session:
            all_inst = session.query(InstalledMod).all()
            installed_by_remote = {(im.source, im.remote_id): im for im in all_inst if im.remote_id}
            installed_by_title = {im.title.lower(): im for im in all_inst if im.title}

            resolved_deps = resolve_mod_dependencies(
                req_mods,
                session,
                installed_by_remote,
                installed_by_title,
            )

        already_installed = [d for d in resolved_deps if d.is_installed or d.status == "INSTALLED"]
        missing_dependencies = [d for d in resolved_deps if not d.is_installed and d.status != "INSTALLED"]

        # Check if there are unresolvable dependencies (partial install allowed)
        not_detected_deps = [
            d for d in missing_dependencies if d.status == "NOT_DETECTED_FINISHED" or not d.remote_id
        ]
        if not_detected_deps:
            names = ", ".join(f"'{d.title}'" for d in not_detected_deps)
            logger.warning(
                f"[INSTALL-DEP] ⚠️ Installation partielle pour '{mod_title}' : "
                f"{len(not_detected_deps)} dépendance(s) introuvables ignorée(s) : {names}"
            )
            # Only install the dependencies that are actually resolvable
            missing_dependencies = [d for d in missing_dependencies if d not in not_detected_deps]

        logger.info(
            f"[INSTALL-DEP] Analyse pour '{mod_title}': {len(resolved_deps)} dépendance(s) au total "
            f"({len(already_installed)} déjà installée(s), {len(missing_dependencies)} à installer, "
            f"{len(not_detected_deps)} non trouvée(s))."
        )

        for dep in already_installed:
            logger.info(f"[INSTALL-DEP] -> Dépendance déjà installée : '{dep.title}' (#{dep.remote_id})")

        total_missing = len(missing_dependencies)
        for idx, dep in enumerate(missing_dependencies, start=1):
            dep_source = dep.source or "loverslab"
            dep_remote_id = dep.remote_id or ""
            dep_title = dep.title or f"Mod #{dep_remote_id}"
            dep_url = dep.url

            # If url is missing, search catalog or fallback to LoversLab file URL
            if not dep_url and dep_remote_id:
                with db.get_session() as s:
                    c_dep = s.query(CatalogMod).filter_by(source=dep_source, remote_id=dep_remote_id).first()
                    if c_dep and c_dep.page_url:
                        dep_url = c_dep.page_url
                if not dep_url and dep_source == "loverslab":
                    dep_url = f"https://www.loverslab.com/files/file/{dep_remote_id}/"

            logger.info(
                f"[INSTALL-DEP] [{idx}/{total_missing}] Démarrage téléchargement & installation dépendance : "
                f"'{dep_title}' (Source: {dep_source}, ID: #{dep_remote_id}, URL: {dep_url})"
            )

            if progress_callback:
                pct = int(10 + (idx - 1) / max(total_missing, 1) * 35)
                progress_callback(
                    pct,
                    f"Installation dépendance ({idx}/{total_missing}) : {dep_title}...",
                    f"ID #{dep_remote_id}",
                )

            if not dep_url:
                logger.error(f"[INSTALL-DEP] ❌ URL introuvable pour '{dep_title}' (#{dep_remote_id}). Installation sautée.")
                continue

            dep_payload = CatalogInstallRequest(
                source=dep_source,
                remote_id=dep_remote_id,
                page_url=dep_url,
                title=dep_title,
                install_dependencies=False,  # Prevent cyclic loops
            )
            dep_res = _perform_install(dep_payload, progress_callback=progress_callback)
            if dep_res.success:
                logger.info(f"[INSTALL-DEP] ✅ [{idx}/{total_missing}] Dépendance '{dep_title}' (#{dep_remote_id}) installée avec succès.")
                installed_dependencies.append(dep_title)
            else:
                err_msg = f"Échec de l'installation de la dépendance requise '{dep_title}': {dep_res.message}"
                logger.error(f"[INSTALL-DEP] ❌ [{idx}/{total_missing}] {err_msg}")
                return CatalogInstallResponse(
                    success=False,
                    message=f"Installation interrompue : {err_msg}",
                    installed_dependencies=installed_dependencies,
                )

    logger.info(f"[INSTALL-MAIN] Démarrage de l'installation du mod principal : '{mod_title}' ({source} #{remote_id})...")

    provider = ProviderRegistry.get_provider(source)
    if not provider:
        return CatalogInstallResponse(success=False, message=f"Fournisseur source '{source}' non supporté.")

    if progress_callback:
        progress_callback(2, "Analyse de la page du mod...", f"Source : {source}")

    details = provider.get_mod_details(page_url)
    download_urls = details.get("download_urls", [])
    if not download_urls:
        ext_links = details.get("external_links", [])
        if ext_links:
            return CatalogInstallResponse(
                success=False, message=f"Téléchargement externe requis : {', '.join(ext_links[:2])}"
            )
        return CatalogInstallResponse(success=False, message="Aucun lien de téléchargement trouvé pour ce mod.")

    dl_info = download_urls[0]
    dl_url = dl_info["url"] if isinstance(dl_info, dict) else dl_info

    temp_dir = Path(tempfile.gettempdir()) / "sims4_mod_manager_downloads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    filename = f"mod_{remote_id}.zip"
    dest_file = temp_dir / filename

    if progress_callback:
        progress_callback(5, "Démarrage du téléchargement...", f"{filename}")

    ok, msg = provider.download_mod_file(dl_url, dest_file, progress_callback=progress_callback)
    if not ok:
        logger.error(f"Échec du téléchargement du mod '{mod_title}' ({source} #{remote_id}): {msg}")
        return CatalogInstallResponse(success=False, message=f"Échec du téléchargement: {msg}")

    file_to_install = Path(msg) if Path(msg).exists() else dest_file
    try:
        with open(file_to_install, "rb") as f:
            magic = f.read(4)
        if magic == b"DBPF" and file_to_install.suffix.lower() != ".package":
            pkg_path = file_to_install.with_suffix(".package")
            file_to_install.replace(pkg_path)
            file_to_install = pkg_path
    except Exception as e:
        logger.debug(f"Vérification DBPF échouée pour {file_to_install}: {e}")

    install_ok, install_msg = ModInstaller.install_mod_from_file(
        file_path=file_to_install,
        catalog_mod=cat_mod,
        source=source,
        custom_title=mod_title,
        version_date=version_date,
        version_str=details.get("version_str", ""),
        progress_callback=progress_callback,
    )

    if not install_ok:
        logger.error(f"Échec de l'installation du mod '{mod_title}' ({source} #{remote_id}): {install_msg}")
    else:
        logger.info(f"Installation réussie du mod '{mod_title}' ({source} #{remote_id})")
        if not_detected_deps:
            names = ", ".join(f"'{d.title}'" for d in not_detected_deps)
            install_msg = (
                f"Installation partielle réussie ! Le mod '{mod_title}' a été installé avec succès, "
                f"mais {len(not_detected_deps)} dépendance(s) introuvable(s) ({names}) n'ont pas pu être ajoutées."
            )

    try:
        file_to_install.unlink(missing_ok=True)
        dest_file.unlink(missing_ok=True)
    except Exception as e:
        logger.debug(f"Nettoyage des fichiers temporaires échoué: {e}")

    return CatalogInstallResponse(
        success=install_ok,
        message=install_msg,
        installed_dependencies=installed_dependencies,
    )


@router.post("/install", response_model=CatalogInstallResponse)
def install_mod(payload: CatalogInstallRequest):
    """Downloads and installs a mod given its catalog id or source and remote_id/page_url."""
    res = _perform_install(payload)
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
