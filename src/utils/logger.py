import sys
import logging
from collections import deque
from typing import List


# Log dir uses the same path as AppConfig.get_app_dir() / "logs"
# Centralized constant to avoid duplicating ".sims4_mod_manager" across modules
_APP_DIR_NAME = ".sims4_mod_manager"


class QtLogHandler(logging.Handler):
    """Logging handler that emits Qt signals for UI streaming.

    Attached lazily via attach_qt_handler() only when a QApplication is running,
    so PySide6 is never imported in headless/server mode.
    """

    def __init__(self, emitter):
        super().__init__()
        self._emitter = emitter
        self.history: deque = deque(maxlen=2000)

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.history.append(msg)
            self._emitter.log_received.emit(msg, record.levelname)
        except (RuntimeError, Exception):
            # Gracefully ignore when Qt application or emitter is shut down
            pass

    def get_history(self) -> List[str]:
        """Returns the log history as a plain list (for backward compatibility)."""
        return list(self.history)


# Module-level reference; set by attach_qt_handler()
_qt_log_handler: QtLogHandler | None = None


def attach_qt_handler(logger_instance: logging.Logger | None = None) -> QtLogHandler:
    """Imports PySide6, creates a QtLogEmitter + QtLogHandler, and attaches it to the logger.

    Call this *once* before QApplication.exec(), and only in GUI mode.
    Returns the handler so the UI can connect to its emitter's signals.
    """
    global _qt_log_handler
    if _qt_log_handler is not None:
        return _qt_log_handler

    from PySide6.QtCore import QObject, Signal

    class QtLogEmitter(QObject):
        log_received = Signal(str, str)  # formatted_message, levelname

    emitter = QtLogEmitter()
    handler = QtLogHandler(emitter)

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG)

    target_logger = logger_instance or logging.getLogger("sims4_mod_manager")
    target_logger.addHandler(handler)

    _qt_log_handler = handler
    return handler


def get_qt_log_handler() -> QtLogHandler | None:
    """Returns the attached Qt log handler, or None if not yet attached."""
    return _qt_log_handler


def setup_logger(name: str = "sims4_mod_manager") -> logging.Logger:
    """Sets up and returns a configured logger with console and file handlers.

    The Qt UI handler is NOT attached here; call attach_qt_handler() separately
    in GUI mode to avoid importing PySide6 in headless/server mode.
    """
    _logger = logging.getLogger(name)
    if _logger.handlers:
        return _logger

    _logger.setLevel(logging.DEBUG)

    # Formatter
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    _logger.addHandler(console_handler)

    # File Handler
    try:
        from src.core.config import AppConfig

        log_dir = AppConfig.get_logs_dir()
        file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        _logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not set up file logger: {e}", file=sys.stderr)

    return _logger


logger = setup_logger()
