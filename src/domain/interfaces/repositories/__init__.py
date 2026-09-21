"""Interfaces des Repositories (API Internes d'accès aux données)."""

from src.domain.interfaces.repositories.account_repository_interface import IAccountRepository
from src.domain.interfaces.repositories.catalog_repository_interface import ICatalogRepository
from src.domain.interfaces.repositories.mod_repository_interface import IInstalledModRepository

__all__ = [
    "IAccountRepository",
    "ICatalogRepository",
    "IInstalledModRepository",
]
