import sys
import logging
from pathlib import Path
from typing import List
from PySide6.QtCore import QObject, Signal


class QtLogEmitter(QObject):
    log_received = Signal(str, str)  # formatted_message, levelname


class QtLogHandler(logging.Handler):
    """Logging handler that emits Qt signals for UI streaming."""

    def __init__(self, emitter: QtLogEmitter):
        super().__init__()
        self.emitter = emitter
        self.history: List[str] = []
        self.max_history = 2000

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.history.append(msg)
            if len(self.history) > self.max_history:
                self.history.pop(0)
            self.emitter.log_received.emit(msg, record.levelname)
        except (RuntimeError, Exception):
            # Gracefully ignore when Qt application or emitter is shut down
            pass


log_emitter = QtLogEmitter()
qt_log_handler = QtLogHandler(log_emitter)


def setup_logger(name: str = "sims4_mod_manager") -> logging.Logger:
    """Sets up and returns a configured logger with console, file, and Qt handlers."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Formatter
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Qt UI Handler
    qt_log_handler.setFormatter(formatter)
    qt_log_handler.setLevel(logging.DEBUG)
    logger.addHandler(qt_log_handler)

    # File Handler
    log_dir = Path.home() / ".sims4_mod_manager" / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not set up file logger: {e}", file=sys.stderr)

    return logger


logger = setup_logger()
