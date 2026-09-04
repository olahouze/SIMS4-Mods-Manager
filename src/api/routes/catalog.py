import json
import queue
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse

from src.api.models import (
    CatalogListResponse,
    CatalogModItem,
    CatalogSyncRequest,
    CatalogSyncStatusResponse,
    CatalogInstallRequest,
    CatalogInstallResponse,
    ModDetailsResponse,
)
from src.core.config import AppConfig
from src.core.database import DatabaseManager, CatalogMod, InstalledMod
from src.core.mod_installer import ModInstaller
from src.core.session_manager import SessionManager
from src.core.update_checker import check_has_update
from src.providers import ProviderRegistry
from src.utils.logger import logger

router = APIRouter(prefix="/catalog", tags=["Catalog"])


# Global Sync Tracker State (§3.3)
class SyncTracker:
    """Thread-safe tracker for catalog synchronization progress."""

    _lock = threading.Lock()
    is_running: bool = False
    progress_percent: int = 0
    message: str = "Prêt"
    total_scraped: int = 0
    pages_completed: int = 0
    page1_ready: bool = False
    last_completed_at: Optional[str] = None

    @classmethod
    def start(cls, max_pages: int) -> None:
        with cls._lock:
            cls.is_running = True
            cls.progress_percent = 0
            cls.message = f"Démarrage de la synchronisation ({max_pages} pages)..."
            cls.total_scraped = 0
            cls.pages_completed = 0
            cls.page1_ready = False

    @classmethod
    def update_progress(cls, percent: int, message: str) -> None:
        with cls._lock:
            cls.progress_percent = percent
            cls.message = message

    @classmethod
    def record_page(cls, new_count: int, is_first_page: bool = False) -> None:
        with cls._lock:
            cls.pages_completed += 1
            cls.total_scraped += new_count
            if is_first_page:
                cls.page1_ready = True

    @classmethod
    def set_error(cls, message: str) -> None:
        with cls._lock:
            cls.message = message

    @classmethod
    def finish(cls, total_new: int) -> None:
        with cls._lock:
            cls.progress_percent = 100
            cls.total_scraped = total_new
            cls.message = f"Synchronisation terminée avec succès ({total_new} nouveaux mods indexés)."
            cls.last_completed_at = datetime.now().isoformat()
            cls.is_running = False

    @classmethod
    def stop(cls) -> None:
        with cls._lock:
            cls.is_running = False

    @classmethod
    def to_response(cls) -> CatalogSyncStatusResponse:
        with cls._lock:
            return CatalogSyncStatusResponse(
                is_running=cls.is_running,
                progress_percent=cls.progress_percent,
                message=cls.message,
                total_scraped=cls.total_scraped,
                pages_completed=cls.pages_completed,
                page1_ready=cls.page1_ready,
                last_completed_at=cls.last_completed_at,
            )


def _run_catalog_sync(max_pages: int):
    """Background task for multi-source scraping with dynamic page count detection, exponential backoff, and progressive saving."""
    db = DatabaseManager.get_instance()
    providers = ProviderRegistry.list_providers()
    total_new = 0

    # Determine page limits per provider (max_pages <= 0 means all available pages on site)
    provider_pages = {}
    for prov in providers:
        if hasattr(prov, "get_total_pages"):
            try:
                avail = prov.get_total_pages()
            except Exception as e:
                logger.debug(f"Erreur détection pages pour {prov.display_name}: {e}")
                avail = 10
            if max_pages <= 0:
                provider_pages[prov] = avail
            else:
                provider_pages[prov] = min(max_pages, avail)
            logger.info(
                f"Source {prov.display_name} : {avail} pages détectées au total sur le site. Synchronisation de {provider_pages[prov]} pages."
            )
        else:
            provider_pages[prov] = max_pages if max_pages > 0 else 5

    total_target_pages = sum(provider_pages.values()) or 1
    SyncTracker.start(total_target_pages)

    try:
        completed_pages = 0
        for prov, target_pages in provider_pages.items():
            for page in range(1, target_pages + 1):
                completed_pages += 1
                pct = int((completed_pages / total_target_pages) * 100)
                msg = f"Synchronisation de {prov.display_name} (Page {page}/{target_pages})..."
                SyncTracker.update_progress(pct, msg)
                logger.info(msg)

                # Retry loop with exponential backoff on failure
                max_retries = 3
                base_delay = 2.0
                mods = []
                scrape_success = False

                for attempt in range(max_retries):
                    try:
                        mods = prov.scrape_catalog(page=page)
                        scrape_success = True
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2**attempt)
                            warn_msg = (
                                f"Échec scraping {prov.display_name} page {page} "
                                f"(tentative {attempt + 1}/{max_retries}). "
                                f"Nouvelle tentative dans {delay:.1f}s... Erreur: {e}"
                            )
                            logger.warning(warn_msg)
                            SyncTracker.update_progress(
                                pct, f"Erreur {prov.display_name} p.{page} - Réessai dans {int(delay)}s..."
                            )
                            time.sleep(delay)
                        else:
                            logger.error(
                                f"Erreur définitive scraping {prov.display_name} page {page}: {e}", exc_info=True
                            )

                if not scrape_success and not mods:
                    continue

                new_on_page = 0
                try:
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
                                    category=m_data.get("category", ""),
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

                    logger.info(f"Page {page} traitée : {len(mods)} mods ({new_on_page} nouveaux).")
                    SyncTracker.record_page(new_on_page, is_first_page=(completed_pages == 1))
                    time.sleep(0.4)
                except Exception as e:
                    logger.error(f"Erreur enregistrement page {page} en BDD: {e}", exc_info=True)

        SyncTracker.finish(total_new)
    except Exception as e:
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
        installed_by_id = {
            im.catalog_mod_id: im for im in all_installed if im.catalog_mod_id and not im.remote_id
        }

        paginated_items = []
        for m in paginated_mods:
            # Canonical match by (source, remote_id) first; fallback to FK only for manual/untracked mods
            inst = installed_by_remote.get((m.source, m.remote_id)) or installed_by_id.get(m.id)
            is_installed = inst is not None
            has_update = check_has_update(inst, m) if is_installed else False

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

    background_tasks.add_task(_run_catalog_sync, payload.max_pages)
    page_msg = "toutes les pages détectées" if payload.max_pages <= 0 else f"{payload.max_pages} pages par source"
    return CatalogSyncStatusResponse(
        is_running=True,
        progress_percent=0,
        message=f"Synchronisation démarrée ({page_msg}).",
        total_scraped=0,
        pages_completed=0,
        page1_ready=False,
        last_completed_at=SyncTracker.last_completed_at,
    )


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
        if (force_refresh or not desc or is_legacy) and m.page_url:
            try:
                provider = ProviderRegistry.get_provider(m.source)
                if provider:
                    details = provider.get_mod_details(m.page_url)
                    fetched_desc = details.get("description", "")
                    if fetched_desc:
                        m.description = fetched_desc
                        desc = fetched_desc
                        session.commit()
            except Exception as e:
                logger.debug(f"Erreur extraction description pour {m.title}: {e}")

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

    try:
        file_to_install.unlink(missing_ok=True)
        dest_file.unlink(missing_ok=True)
    except Exception as e:
        logger.debug(f"Nettoyage des fichiers temporaires échoué: {e}")

    return CatalogInstallResponse(success=install_ok, message=install_msg)


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
