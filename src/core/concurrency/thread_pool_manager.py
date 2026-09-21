"""Gestionnaire centralisé et borné des pools de threads (Backend Concurrency).

Fournit des pools distincts pour les opérations I/O et CPU-bound, évitant la
multiplication incontrôlée de threads dans l'application et assurant un arrêt
propre et gracieux à la fermeture.
"""

from __future__ import annotations

import concurrent.futures
import os
import threading
from typing import Any, Callable, Optional, TypeVar

from src.core.shutdown_manager import ShutdownManager
from src.utils.logger import logger

T = TypeVar("T")


class ThreadPoolManager:
    """Gestionnaire singleton de pools de threads bornés pour le backend."""

    _instance: Optional["ThreadPoolManager"] = None
    _lock = threading.Lock()

    def __init__(self, max_io_workers: int = 8, max_cpu_workers: Optional[int] = None) -> None:
        cpu_count = os.cpu_count() or 4
        self._max_io_workers = max(2, max_io_workers)
        self._max_cpu_workers = max_cpu_workers or max(2, min(cpu_count, 8))

        self._io_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_io_workers,
            thread_name_prefix="SIMS4-IO-Worker",
        )
        self._cpu_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_cpu_workers,
            thread_name_prefix="SIMS4-CPU-Worker",
        )

        self._active_futures: set[concurrent.futures.Future[Any]] = set()
        self._futures_lock = threading.Lock()

        # Enregistrement pour l'arrêt propre
        ShutdownManager.register_callback(self.shutdown)
        logger.info(
            f"ThreadPoolManager initialisé (I/O workers: {self._max_io_workers}, CPU workers: {self._max_cpu_workers})"
        )

    @classmethod
    def get_instance(cls) -> "ThreadPoolManager":
        """Accès thread-safe au singleton ThreadPoolManager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ThreadPoolManager()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Réinitialise l'instance (utile pour l'isolation des tests)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.shutdown(wait=False, cancel_futures=True)
                cls._instance = None

    def submit_io(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> concurrent.futures.Future[T]:
        """Soumet une tâche I/O (téléchargement, scraping, réseau)."""
        if ShutdownManager.is_shutting_down():
            raise RuntimeError("Impossible de soumettre une tâche : arrêt en cours.")
        future = self._io_executor.submit(fn, *args, **kwargs)
        self._track_future(future)
        return future

    def submit_cpu(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> concurrent.futures.Future[T]:
        """Soumet une tâche CPU-bound (décompression 7z/zip, hash, parsing)."""
        if ShutdownManager.is_shutting_down():
            raise RuntimeError("Impossible de soumettre une tâche : arrêt en cours.")
        future = self._cpu_executor.submit(fn, *args, **kwargs)
        self._track_future(future)
        return future

    def _track_future(self, future: concurrent.futures.Future[Any]) -> None:
        """Garde une trace des futures actives pour l'annulation lors du shutdown."""
        with self._futures_lock:
            self._active_futures.add(future)
        future.add_done_callback(self._untrack_future)

    def _untrack_future(self, future: concurrent.futures.Future[Any]) -> None:
        with self._futures_lock:
            self._active_futures.discard(future)

    def shutdown(self, wait: bool = False, cancel_futures: bool = True) -> None:
        """Arrête proprement les exécuteurs et annule les tâches en attente."""
        logger.info("Arrêt gracieux de ThreadPoolManager...")
        with self._futures_lock:
            if cancel_futures:
                for f in self._active_futures:
                    f.cancel()
                self._active_futures.clear()

        try:
            self._io_executor.shutdown(wait=wait, cancel_futures=cancel_futures)
            self._cpu_executor.shutdown(wait=wait, cancel_futures=cancel_futures)
        except Exception as e:
            logger.debug(f"Avertissement lors de la fermeture des pools : {e}")
