"""Worker générique QRunnable avec signaux Qt pour l'exécution non-bloquante dans l'UI."""

from __future__ import annotations

import traceback
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from src.utils.logger import logger


class WorkerSignals(QObject):
    """Signaux Qt pour la communication entre le worker d'arrière-plan et le thread GUI."""

    started = Signal()
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int, str)


class GenericRunnable(QRunnable):
    """Exécuteur générique basé sur QRunnable pour soumettre des tâches au QThreadPool de Qt."""

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """Exécute la fonction cible et transmet le résultat ou l'erreur via les signaux."""
        self.signals.started.emit()
        try:
            # Vérifie si la fonction accepte un progress_callback
            if "progress_callback" in self.fn.__code__.co_varnames:

                def _prog(pct: int, msg: str = ""):
                    self.signals.progress.emit(pct, msg)

                self.kwargs["progress_callback"] = _prog

            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            logger.error(f"Erreur dans GenericRunnable: {e}\n{traceback.format_exc()}")
            self.signals.error.emit(str(e))


def run_async_ui_task(
    fn: Callable[..., Any],
    on_finished: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[int, str], None]] = None,
    *args: Any,
    **kwargs: Any,
) -> GenericRunnable:
    """Helper pratique pour exécuter une tâche d'arrière-plan sur le QThreadPool global."""
    worker = GenericRunnable(fn, *args, **kwargs)
    if on_finished:
        worker.signals.finished.connect(on_finished)
    if on_error:
        worker.signals.error.connect(on_error)
    if on_progress:
        worker.signals.progress.connect(on_progress)

    QThreadPool.globalInstance().start(worker)
    return worker
