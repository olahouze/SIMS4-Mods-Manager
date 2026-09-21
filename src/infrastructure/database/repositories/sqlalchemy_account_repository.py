"""Implémentation SQLAlchemy de l'API Interne IAccountRepository."""

from __future__ import annotations

from typing import Optional

from src.database.manager import DatabaseManager
from src.database.models import AccountSession
from src.domain.interfaces.repositories.account_repository_interface import IAccountRepository
from src.domain.models.account_entity import AccountSessionEntity
from src.infrastructure.database.repositories.mappers import ModelMapper


class SqlAlchemyAccountRepository(IAccountRepository):
    """Repository gérant la persistance des sessions de comptes de providers via SQLAlchemy."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self._custom_db_manager = db_manager

    @property
    def db_manager(self) -> DatabaseManager:
        """Exécute l'opération db manager.

        Returns:
            Résultat de l'opération db_manager.
        """
        return self._custom_db_manager or DatabaseManager.get_instance()

    def get_by_provider(self, provider_name: str) -> Optional[AccountSessionEntity]:
        """Exécute l'opération get by provider.

        Args:
            provider_name: Paramètre provider_name.

        Returns:
            Résultat de l'opération get_by_provider.
        """
        with self.db_manager.get_session() as session:
            model = session.query(AccountSession).filter(AccountSession.provider_name == provider_name.lower()).first()
            return ModelMapper.account_to_entity(model) if model else None

    def get_all(self) -> list[AccountSessionEntity]:
        """Exécute l'opération get all.

        Returns:
            Résultat de l'opération get_all.
        """
        with self.db_manager.get_session() as session:
            models = session.query(AccountSession).all()
            return [ModelMapper.account_to_entity(m) for m in models]

    def save(self, entity: AccountSessionEntity) -> AccountSessionEntity:
        """Exécute l'opération save.

        Args:
            entity: Paramètre entity.

        Returns:
            Résultat de l'opération save.
        """
        with self.db_manager.get_session() as session:
            model = (
                session.query(AccountSession)
                .filter(AccountSession.provider_name == entity.provider_name.lower())
                .first()
            )
            if model:
                ModelMapper.account_to_model(entity, model)
            else:
                model = ModelMapper.account_to_model(entity)
                session.add(model)
            session.commit()
            session.refresh(model)
            return ModelMapper.account_to_entity(model)

    def delete(self, provider_name: str) -> bool:
        """Exécute l'opération delete.

        Args:
            provider_name: Paramètre provider_name.

        Returns:
            Résultat de l'opération delete.
        """
        with self.db_manager.get_session() as session:
            model = session.query(AccountSession).filter(AccountSession.provider_name == provider_name.lower()).first()
            if not model:
                return False
            session.delete(model)
            session.commit()
            return True
