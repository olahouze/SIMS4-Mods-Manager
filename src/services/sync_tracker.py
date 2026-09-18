"""
Thread-safe tracker for catalog synchronization progress with pause and stop support.
"""
import threading
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.api.schemas.catalog import (
    CatalogSyncStatusResponse,
    SubCategoryProgress,
)
from src.database.manager import DatabaseManager
from src.core.shutdown_manager import ShutdownManager
from src.utils.logger import logger


class SyncTracker:
    """Thread-safe tracker for catalog synchronization progress with pause and stop support."""

    _lock = threading.RLock()
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
    def start(
        cls,
        max_pages: int,
        categories_list: Optional[List[Dict[str, Any]]] = None,
        max_pages_per_cat: int = 0,
    ) -> None:
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
                        "total_pages": (
                            c.get("default_pages", 1)
                            if max_pages_per_cat <= 0
                            else min(max_pages_per_cat, c.get("default_pages", 1))
                        ),
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
