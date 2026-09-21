"""Bridge de compatibilité vers src.infrastructure.database.models."""

from src.infrastructure.database.models import (
    AccountSession,
    Base,
    CatalogMod,
    InstalledMod,
)

__all__ = ["AccountSession", "Base", "CatalogMod", "InstalledMod"]
