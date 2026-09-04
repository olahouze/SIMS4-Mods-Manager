import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from src.api.models import (
    CatalogListResponse,
    CatalogModItem,
    CatalogSyncRequest,
    CatalogSyncStatusResponse,
    CatalogInstallRequest,
    CatalogInstallResponse,
    ModDetailsResponse,
)
from src.core.database import DatabaseManager, CatalogMod, InstalledMod
from src.core.mod_installer import ModInstaller
from src.providers import ProviderRegistry
from src.utils.logger import logger

router = APIRouter(prefix="/catalog", tags=["Catalog"])


# Global Sync Tracker State
class SyncTracker:
    _lock = threading.Lock()
    is_running: bool = False
    progress_percent: int = 0
    message: str = "Prêt"
    total_scraped: int = 0
    pages_completed: int = 0
    page1_ready: bool = False
    last_completed_at: Optional[str] = None


def _run_catalog_sync(max_pages: int):
    """Background task for multi-source scraping with exponential backoff and progressive saving."""
    with SyncTracker._lock:
        SyncTracker.is_running = True
        SyncTracker.progress_percent = 0
        SyncTracker.message = f"Démarrage de la synchronisation ({max_pages} pages)..."
        SyncTracker.total_scraped = 0
        SyncTracker.pages_completed = 0
        SyncTracker.page1_ready = False

    db = DatabaseManager.get_instance()
    providers = ProviderRegistry.list_providers()
    total_new = 0

    try:
        for prov_idx, provider in enumerate(providers):
            for page in range(1, max_pages + 1):
                pct = int(((page - 1 + (prov_idx * max_pages)) / (len(providers) * max_pages)) * 100)
                msg = f"Synchronisation de {provider.display_name} (Page {page}/{max_pages})..."
                with SyncTracker._lock:
                    SyncTracker.progress_percent = pct
                    SyncTracker.message = msg
                logger.info(msg)

                # Retry loop with exponential backoff on failure
                max_retries = 3
                base_delay = 2.0
                mods = []
                scrape_success = False

                for attempt in range(max_retries):
                    try:
                        mods = provider.scrape_catalog(page=page)
                        scrape_success = True
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2**attempt)
                            warn_msg = (
                                f"Échec scraping {provider.display_name} page {page} "
                                f"(tentative {attempt + 1}/{max_retries}). "
                                f"Nouvelle tentative dans {delay:.1f}s... Erreur: {e}"
                            )
                            logger.warning(warn_msg)
                            with SyncTracker._lock:
                                SyncTracker.message = (
                                    f"Erreur {provider.display_name} p.{page} - Réessai dans {int(delay)}s..."
                                )
                            time.sleep(delay)
                        else:
                            logger.error(
                                f"Erreur définitive scraping {provider.display_name} page {page}: {e}", exc_info=True
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

                    with SyncTracker._lock:
                        SyncTracker.pages_completed += 1
                        SyncTracker.total_scraped = total_new
                        if page == 1:
                            SyncTracker.page1_ready = True
                except Exception as e:
                    logger.error(f"Erreur enregistrement page {page} en BDD: {e}", exc_info=True)

        with SyncTracker._lock:
            SyncTracker.progress_percent = 100
            SyncTracker.total_scraped = total_new
            SyncTracker.message = f"Synchronisation terminée avec succès ({total_new} nouveaux mods indexés)."
            SyncTracker.last_completed_at = datetime.now().isoformat()
    except Exception as e:
        with SyncTracker._lock:
            SyncTracker.message = f"Erreur de synchronisation: {e}"
    finally:
        with SyncTracker._lock:
            SyncTracker.is_running = False


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
    """Returns catalog mods with filtering, search, status, and pagination."""
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

        if sort == "az":
            query = query.order_by(CatalogMod.title.asc())
        else:
            query = query.order_by(CatalogMod.updated_date.desc().nullslast())

        # Pre-fetch installed map
        installed_map = {(im.source, im.remote_id): im for im in session.query(InstalledMod).all()}

        all_results = query.all()
        filtered_items = []

        for m in all_results:
            inst = installed_map.get((m.source, m.remote_id))
            is_installed = inst is not None
            has_update = False
            if is_installed and m.updated_date and inst.version_date:
                has_update = m.updated_date > inst.version_date

            if status == "installed" and not is_installed:
                continue
            elif status == "not_installed" and is_installed:
                continue
            elif status == "updates_available" and not has_update:
                continue

            filtered_items.append(
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

        total = len(filtered_items)
        start_idx = (page - 1) * limit
        paginated_items = filtered_items[start_idx : start_idx + limit]

        return CatalogListResponse(
            total=total,
            page=page,
            limit=limit,
            items=paginated_items,
        )


@router.post("/sync", response_model=CatalogSyncStatusResponse)
def start_sync(payload: CatalogSyncRequest, background_tasks: BackgroundTasks):
    """Triggers multi-source catalog synchronization."""
    with SyncTracker._lock:
        if SyncTracker.is_running:
            return CatalogSyncStatusResponse(
                is_running=True,
                progress_percent=SyncTracker.progress_percent,
                message="Une synchronisation est déjà en cours d'exécution.",
                total_scraped=SyncTracker.total_scraped,
                pages_completed=SyncTracker.pages_completed,
                page1_ready=SyncTracker.page1_ready,
                last_completed_at=SyncTracker.last_completed_at,
            )

    background_tasks.add_task(_run_catalog_sync, payload.max_pages)
    return CatalogSyncStatusResponse(
        is_running=True,
        progress_percent=0,
        message=f"Synchronisation démarrée ({payload.max_pages} pages par source).",
        total_scraped=0,
        pages_completed=0,
        page1_ready=False,
        last_completed_at=SyncTracker.last_completed_at,
    )


@router.get("/sync/status", response_model=CatalogSyncStatusResponse)
def get_sync_status():
    """Returns current catalog scraping progress status."""
    with SyncTracker._lock:
        return CatalogSyncStatusResponse(
            is_running=SyncTracker.is_running,
            progress_percent=SyncTracker.progress_percent,
            message=SyncTracker.message,
            total_scraped=SyncTracker.total_scraped,
            pages_completed=SyncTracker.pages_completed,
            page1_ready=SyncTracker.page1_ready,
            last_completed_at=SyncTracker.last_completed_at,
        )


@router.get("/{mod_id}/details", response_model=ModDetailsResponse)
def get_catalog_mod_details(mod_id: int, force_refresh: bool = False):
    """Returns detailed mod information including full description/message and gallery from mod page."""
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        m = session.query(CatalogMod).filter_by(id=mod_id).first()
        if not m:
            raise HTTPException(status_code=404, detail="Mod introuvable dans le catalogue.")

        desc = m.description or ""
        is_legacy = bool(
            desc
            and (
                "What's New in Version" in desc
                or "About This File" in desc
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
    except Exception:
        pass

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
    except Exception:
        pass

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
    """
    Downloads and installs a mod while streaming real-time progress events as newline-delimited JSON.
    """
    import json
    import queue
    from fastapi.responses import StreamingResponse

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


@router.get("/thumbnail")
def get_thumbnail(source: str, remote_id: str, url: str):
    """Fetches and caches thumbnail image for catalog mod, returning the file."""
    from fastapi.responses import FileResponse
    from src.core.config import AppConfig
    from src.core.session_manager import SessionManager

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
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Erreur téléchargement image: {e}")

    return FileResponse(dest_path, media_type="image/jpeg")


@router.post("/purge")
def purge_catalog_endpoint():
    """Purges all catalog mods to restart from a clean catalog."""
    db = DatabaseManager.get_instance()
    deleted = db.purge_catalog()
    return {"success": True, "deleted": deleted, "message": f"{deleted} mod(s) supprimé(s) du catalogue."}
