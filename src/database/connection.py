"""Bridge de compatibilité vers src.infrastructure.database.connection."""

from src.infrastructure.database.connection import (
    create_db_engine,
    get_default_db_path,
    get_session_factory,
    init_db_schema,
)

__all__ = [
    "create_db_engine",
    "get_default_db_path",
    "get_session_factory",
    "init_db_schema",
]
