"""Implémentation SQLAlchemy de l'API Interne IInstalledModRepository."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import joinedload

from src.database.manager import DatabaseManager
from src.database.models import InstalledMod
from src.domain.interfaces.repositories.mod_repository_interface import IInstalledModRepository
from src.domain.models.mod_entity import InstalledModEntity
from src.infrastructure.database.repositories.mappers import ModelMapper


class SqlAlchemyInstalledModRepository(IInstalledModRepository):
    """Repository gérant la persistance des mods installés via SQLAlchemy."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self._custom_db_manager = db_manager

    @property
    def db_manager(self) -> DatabaseManager:
        """Exécute l'opération db manager.

        Returns:
            Résultat de l'opération db_manager.
        """
        return self._custom_db_manager or DatabaseManager.get_instance()

    def get_by_id(self, mod_id: int) -> Optional[InstalledModEntity]:
        """Exécute l'opération get by id.

        Args:
            mod_id: Paramètre mod_id.

        Returns:
            Résultat de l'opération get_by_id.
        """
        with self.db_manager.get_session() as session:
            model = (
                session.query(InstalledMod)
                .options(joinedload(InstalledMod.catalog_mod))
                .filter(InstalledMod.id == mod_id)
                .first()
            )
            return ModelMapper.installed_to_entity(model) if model else None

    def get_by_folder_name(self, folder_name: str) -> Optional[InstalledModEntity]:
        """Exécute l'opération get by folder name.

        Args:
            folder_name: Paramètre folder_name.

        Returns:
            Résultat de l'opération get_by_folder_name.
        """
        with self.db_manager.get_session() as session:
            model = (
                session.query(InstalledMod)
                .options(joinedload(InstalledMod.catalog_mod))
                .filter(InstalledMod.folder_name == folder_name)
                .first()
            )
            return ModelMapper.installed_to_entity(model) if model else None

    def get_by_source_and_remote_id(self, source: str, remote_id: str) -> Optional[InstalledModEntity]:
        """Exécute l'opération get by source and remote id.

        Args:
            source: Paramètre source.
            remote_id: Paramètre remote_id.

        Returns:
            Résultat de l'opération get_by_source_and_remote_id.
        """
        with self.db_manager.get_session() as session:
            model = (
                session.query(InstalledMod)
                .options(joinedload(InstalledMod.catalog_mod))
                .filter(InstalledMod.source == source, InstalledMod.remote_id == remote_id)
                .first()
            )
            return ModelMapper.installed_to_entity(model) if model else None

    def get_all(self, enabled_only: Optional[bool] = None) -> list[InstalledModEntity]:
        """Exécute l'opération get all.

        Args:
            enabled_only: Paramètre enabled_only.

        Returns:
            Résultat de l'opération get_all.
        """
        with self.db_manager.get_session() as session:
            query = session.query(InstalledMod).options(joinedload(InstalledMod.catalog_mod))
            if enabled_only is not None:
                query = query.filter(InstalledMod.is_enabled == enabled_only)
            models = query.order_by(InstalledMod.title.asc()).all()
            return [ModelMapper.installed_to_entity(m) for m in models]

    def save(self, entity: InstalledModEntity) -> InstalledModEntity:
        """Exécute l'opération save.

        Args:
            entity: Paramètre entity.

        Returns:
            Résultat de l'opération save.
        """
        with self.db_manager.get_session() as session:
            model: Optional[InstalledMod] = None
            if entity.id is not None:
                model = session.query(InstalledMod).filter(InstalledMod.id == entity.id).first()
            if not model and entity.folder_name:
                model = session.query(InstalledMod).filter(InstalledMod.folder_name == entity.folder_name).first()

            if model:
                ModelMapper.installed_to_model(entity, model)
            else:
                model = ModelMapper.installed_to_model(entity)
                session.add(model)

            session.commit()
            session.refresh(model)
            return ModelMapper.installed_to_entity(model)

    def delete_by_id(self, mod_id: int) -> bool:
        """Exécute l'opération delete by id.

        Args:
            mod_id: Paramètre mod_id.

        Returns:
            Résultat de l'opération delete_by_id.
        """
        with self.db_manager.get_session() as session:
            model = session.query(InstalledMod).filter(InstalledMod.id == mod_id).first()
            if not model:
                return False
            session.delete(model)
            session.commit()
            return True

    def set_enabled(self, mod_id: int, is_enabled: bool) -> bool:
        """Exécute l'opération set enabled.

        Args:
            mod_id: Paramètre mod_id.
            is_enabled: Paramètre is_enabled.

        Returns:
            Résultat de l'opération set_enabled.
        """
        with self.db_manager.get_session() as session:
            model = session.query(InstalledMod).filter(InstalledMod.id == mod_id).first()
            if not model:
                return False
            model.is_enabled = is_enabled
            session.commit()
            return True

    def count(self) -> int:
        """Exécute l'opération count.

        Returns:
            Résultat de l'opération count.
        """
        with self.db_manager.get_session() as session:
            return session.query(InstalledMod).count()
