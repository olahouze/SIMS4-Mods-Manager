import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.api.schemas.catalog import (
    CatalogSyncStatusResponse,
    SubCategoryProgress,
    DependenciesCheckResponse,
)
from src.database.manager import DatabaseManager
from src.database.models import CatalogMod, InstalledMod
from src.core.shutdown_manager import ShutdownManager
from src.providers import ProviderRegistry
from src.services.dependency_resolver import resolve_mod_dependencies
from src.utils.logger import logger


class SyncTracker:
    """Thread-safe tracker for catalog synchronization progress with pause and stop support."""

    _lock = threading.Lock()
    _pause_event = threading.Event()
    _pause_event.set()  # Initially unpaused

    is_running: bool = False
    is_paused: bool = False
    is_stopped: bool = False
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
    _cached_db_count: int = 0
    _last_count_time: float = 0.0

    @classmethod
    def start(cls, max_pages: int, categories_list: Optional[List[Dict[str, Any]]] = None) -> None:
        with cls._lock:
            cls.is_running = True
            cls.is_paused = False
            cls.is_stopped = False
            cls.stop_requested = False
            cls._pause_event.set()
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
            try:
                cls._cached_db_count = DatabaseManager.get_instance().get_catalog_mods_count()
                cls._last_count_time = time.time()
            except Exception:
                pass
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
    def pause(cls, provider: Optional[str] = None) -> None:
        """Pauses background scraping workers non-CPU-intensively."""
        with cls._lock:
            if not cls.is_running or cls.is_paused:
                return
            cls.is_paused = True
            cls._pause_event.clear()
            target_provider = provider or "loverslab"
            cls.providers_status[target_provider] = "PAUSED"
            cls.message = "Synchronisation en pause."
            logger.info(f"Synchronisation mise en pause pour {target_provider}.")

    @classmethod
    def resume(cls, provider: Optional[str] = None) -> None:
        """Resumes background scraping workers."""
        with cls._lock:
            if not cls.is_running or not cls.is_paused:
                return
            cls.is_paused = False
            cls._pause_event.set()
            target_provider = provider or "loverslab"
            cls.providers_status[target_provider] = "RUNNING"
            cls.message = "Synchronisation reprise."
            logger.info(f"Synchronisation reprise pour {target_provider}.")

    @classmethod
    def wait_if_paused(cls) -> None:
        """Blocks worker thread safely if paused until resumed, stopped, or shutting down."""
        while cls.is_paused and not cls.stop_requested and not ShutdownManager.is_shutting_down():
            cls._pause_event.wait(timeout=0.2)

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
            cls.is_paused = False
            cls.is_stopped = False
            cls.providers_status["loverslab"] = "OK"
            try:
                cls._cached_db_count = DatabaseManager.get_instance().get_catalog_mods_count()
                cls._last_count_time = time.time()
            except Exception:
                pass
            for cat_info in cls.categories.values():
                if cat_info.get("status") in ["IN_PROGRESS", "PENDING"]:
                    cat_info["status"] = "COMPLETED"

    @classmethod
    def stop(cls, provider: Optional[str] = None) -> None:
        """Stops background scraping workers cleanly."""
        with cls._lock:
            cls.is_running = False
            cls.is_paused = False
            cls.is_stopped = True
            cls.stop_requested = True
            cls._pause_event.set()  # Unblock workers waiting in pause so they exit immediately
            target_provider = provider or "loverslab"
            if not cls.has_error:
                cls.providers_status[target_provider] = "STOPPED"
            cls.message = "Synchronisation arrêtée."
            logger.info(f"Synchronisation arrêtée pour {target_provider}.")

    @classmethod
    def reset(cls) -> None:
        """Resets tracker state to default idle state (for tests and reinitialization)."""
        with cls._lock:
            cls.is_running = False
            cls.is_paused = False
            cls.is_stopped = False
            cls.stop_requested = False
            cls._pause_event.set()
            cls.progress_percent = 0
            cls.message = "Prêt"
            cls.total_scraped = 0
            cls.pages_completed = 0
            cls.total_pages = 0
            cls.current_category = None
            cls.has_error = False
            cls.error_message = None
            cls.page1_ready = False
            cls.categories.clear()
            cls.providers_status = {"loverslab": "OK", "patreon": "OK"}

    @classmethod
    def to_response(cls) -> CatalogSyncStatusResponse:
        with cls._lock:
            now = time.time()
            if not cls.is_running or (now - cls._last_count_time) > 10.0 or cls._cached_db_count == 0:
                try:
                    cls._cached_db_count = DatabaseManager.get_instance().get_catalog_mods_count()
                    cls._last_count_time = now
                except Exception:
                    pass
            db_count = cls._cached_db_count
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
                is_paused=cls.is_paused,
                is_stopped=cls.is_stopped,
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


def run_catalog_sync(max_pages: int) -> None:
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
                SyncTracker.wait_if_paused()
                if SyncTracker.stop_requested or ShutdownManager.is_shutting_down():
                    break

                max_retries = 3
                base_delay = 2.0
                mods = []
                scrape_success = False

                for attempt in range(max_retries):
                    SyncTracker.wait_if_paused()
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

                SyncTracker.wait_if_paused()
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
                            remote_ids = [m["remote_id"] for m in mods if m.get("remote_id")]
                            existing_map = {}
                            if remote_ids:
                                found = (
                                    session.query(CatalogMod)
                                    .filter(CatalogMod.remote_id.in_(remote_ids))
                                    .all()
                                )
                                existing_map = {(m.source, m.remote_id): m for m in found}

                            for m_data in mods:
                                existing = existing_map.get((m_data["source"], m_data["remote_id"]))
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
                SyncTracker.wait_if_paused()
                if SyncTracker.stop_requested or ShutdownManager.is_shutting_down():
                    break
                time.sleep(0.3)

            if SyncTracker.stop_requested or ShutdownManager.is_shutting_down():
                SyncTracker.update_category(cat_id, min(p, target_cat_pages), target_cat_pages, cat_mods_count, "STOPPED")
            else:
                SyncTracker.update_category(cat_id, target_cat_pages, target_cat_pages, cat_mods_count, "COMPLETED")
            return cat_mods_count

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
        if SyncTracker.is_running:
            SyncTracker.stop()


def check_catalog_dependencies(
    mod_title: str,
    page_url: Optional[str],
    source: str,
    cat_mod: Optional[CatalogMod] = None,
) -> DependenciesCheckResponse:
    """Vérifie l'état de résolution des dépendances d'un mod catalogue."""
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        if not cat_mod and page_url:
            cat_mod = session.query(CatalogMod).filter_by(page_url=page_url).first()

        req_mods = cat_mod.get_requirements_mods_list() if cat_mod else []
        req_status = cat_mod.requirements_status if cat_mod else "NONE"

        # If mod has not been scraped for requirements yet, do so now
        if cat_mod and (not cat_mod.requirements_status or cat_mod.requirements_status == "NONE") and page_url:
            try:
                provider = ProviderRegistry.get_provider(source)
                if provider:
                    logger.info(f"Vérification temps réel des dépendances pour {mod_title} ({page_url})...")
                    det = provider.get_mod_details(page_url)
                    if det.get("requirements_text") is not None or det.get("requirements_status"):
                        cat_mod.requirements_text = det.get("requirements_text")
                        cat_mod.requirements_status = det.get("requirements_status", "NONE")
                        cat_mod.set_requirements_mods_list(det.get("requirements_mods", []))
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

        overrides = cat_mod.get_requirements_overrides() if cat_mod else {}
        dep_items = resolve_mod_dependencies(
            req_mods,
            session,
            installed_by_remote,
            installed_by_title,
            is_syncing=SyncTracker.is_running,
            requirements_overrides=overrides,
        )

        game_dlcs = [d for d in dep_items if d.is_game_dlc or d.status == "GAME_DLC"]
        comment_deps = [d for d in dep_items if d.is_comment or d.status == "COMMENT_NOISE"]
        mod_deps = [
            d for d in dep_items
            if not (d.is_game_dlc or d.status == "GAME_DLC" or d.is_comment or d.status == "COMMENT_NOISE")
        ]

        already_installed = [d for d in mod_deps if d.is_installed or d.status == "INSTALLED"]
        missing = [d for d in mod_deps if not d.is_installed and d.status != "INSTALLED"]

        not_detected_finished = [d for d in missing if d.status == "NOT_DETECTED_FINISHED"]
        not_detected_scanning = [d for d in missing if d.status == "NOT_DETECTED_SCANNING"]
        unresolved_text_deps = [
            d for d in missing if not d.remote_id and d not in not_detected_finished and d not in not_detected_scanning
        ]

        unfound = list(not_detected_finished) + list(unresolved_text_deps)
        found_missing = [d for d in missing if d not in unfound and d.status != "NOT_DETECTED_SCANNING"]
        is_partial = bool(unfound or (req_status == "PENDING_VERIFICATION" and not mod_deps and not game_dlcs))

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
                game_dlc_dependencies=game_dlcs,
                comment_dependencies=comment_deps,
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
                game_dlc_dependencies=game_dlcs,
                comment_dependencies=comment_deps,
            )
        else:
            final_status = "RESOLVED" if (req_mods or game_dlcs) else (req_status or "NONE")
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
                game_dlc_dependencies=game_dlcs,
                comment_dependencies=comment_deps,
            )
