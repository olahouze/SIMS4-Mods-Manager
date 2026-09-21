"""Module d'archive réexportant les fonctions depuis l'infrastructure filesystem (rétrocompatibilité)."""

from src.infrastructure.filesystem.archive_extractor import (
    ArchiveExtractor,
    create_backup_zip,
    extract_archive,
    is_archive,
)

__all__ = [
    "ArchiveExtractor",
    "create_backup_zip",
    "extract_archive",
    "is_archive",
]
