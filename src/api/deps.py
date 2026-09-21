"""Dépendances FastAPI pour l'injection des Repositories et Services (API Internes)."""

from __future__ import annotations

from typing import Generator
from sqlalchemy.orm import Session

from src.database.manager import DatabaseManager
from src.domain.interfaces.repositories.account_repository_interface import IAccountRepository
from src.domain.interfaces.repositories.catalog_repository_interface import ICatalogRepository
from src.domain.interfaces.repositories.mod_repository_interface import IInstalledModRepository
from src.infrastructure.database.repositories.sqlalchemy_account_repository import (
    SqlAlchemyAccountRepository,
)
from src.infrastructure.database.repositories.sqlalchemy_catalog_repository import (
    SqlAlchemyCatalogRepository,
)
from src.infrastructure.database.repositories.sqlalchemy_installed_mod_repository import (
    SqlAlchemyInstalledModRepository,
)

# Instances partagées des repositories
_installed_mod_repo = SqlAlchemyInstalledModRepository()
_catalog_repo = SqlAlchemyCatalogRepository()
_account_repo = SqlAlchemyAccountRepository()


def get_installed_repo() -> IInstalledModRepository:
    """Fournit l'implémentation de l'API interne IInstalledModRepository."""
    return _installed_mod_repo


def get_catalog_repo() -> ICatalogRepository:
    """Fournit l'implémentation de l'API interne ICatalogRepository."""
    return _catalog_repo


def get_account_repo() -> IAccountRepository:
    """Fournit l'implémentation de l'API interne IAccountRepository."""
    return _account_repo


def get_db() -> Generator[Session, None, None]:
    """Générateur de session SQLAlchemy (conservé pour compatibilité interne)."""
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        yield session
