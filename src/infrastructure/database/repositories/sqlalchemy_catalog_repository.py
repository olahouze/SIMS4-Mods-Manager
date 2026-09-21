"""Implémentation SQLAlchemy de l'API Interne ICatalogRepository."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import distinct

from src.database.manager import DatabaseManager
from src.database.models import CatalogMod
from src.domain.interfaces.repositories.catalog_repository_interface import ICatalogRepository
from src.domain.models.mod_entity import CatalogModEntity
from src.infrastructure.database.catalog_queries import build_catalog_query
from src.infrastructure.database.repositories.mappers import ModelMapper


class SqlAlchemyCatalogRepository(ICatalogRepository):
    """Repository gérant la persistance et les recherches dans le catalogue distant via SQLAlchemy."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self._custom_db_manager = db_manager

    @property
    def db_manager(self) -> DatabaseManager:
        return self._custom_db_manager or DatabaseManager.get_instance()

    def get_by_id(self, mod_id: int) -> Optional[CatalogModEntity]:
        with self.db_manager.get_session() as session:
            model = session.query(CatalogMod).filter(CatalogMod.id == mod_id).first()
            return ModelMapper.catalog_to_entity(model) if model else None

    def get_by_source_and_remote_id(self, source: str, remote_id: str) -> Optional[CatalogModEntity]:
        with self.db_manager.get_session() as session:
            model = (
                session.query(CatalogMod).filter(CatalogMod.source == source, CatalogMod.remote_id == remote_id).first()
            )
            return ModelMapper.catalog_to_entity(model) if model else None

    def search(
        self,
        query: str = "",
        category: str = "",
        author: str = "",
        source: str = "all",
        access: str = "all",
        status: str = "all",
        mod_type: str = "all",
        sort: str = "recent",
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "updated_date",
        sort_order: str = "desc",
    ) -> tuple[list[CatalogModEntity], int]:
        with self.db_manager.get_session() as session:
            q = build_catalog_query(
                session=session,
                search=query,
                source=source,
                access=access,
                status=status,
                mod_type=mod_type,
                sort=sort,
            )
            if category and category.lower() != "all":
                q = q.filter(CatalogMod.category == category)
            if author:
                q = q.filter(CatalogMod.author.ilike(f"%{author.strip()}%"))

            total_count = q.count()
            models = q.offset(offset).limit(limit).all()
            return [ModelMapper.catalog_to_entity(m) for m in models], total_count

    def get_all(self, limit: Optional[int] = None, offset: int = 0) -> list[CatalogModEntity]:
        with self.db_manager.get_session() as session:
            q = session.query(CatalogMod).order_by(CatalogMod.title.asc())
            if offset > 0:
                q = q.offset(offset)
            if limit is not None:
                q = q.limit(limit)
            models = q.all()
            return [ModelMapper.catalog_to_entity(m) for m in models]

    def save(self, entity: CatalogModEntity) -> CatalogModEntity:
        with self.db_manager.get_session() as session:
            model: Optional[CatalogMod] = None
            if entity.id is not None:
                model = session.query(CatalogMod).filter(CatalogMod.id == entity.id).first()
            if not model and entity.source and entity.remote_id:
                model = (
                    session.query(CatalogMod)
                    .filter(CatalogMod.source == entity.source, CatalogMod.remote_id == entity.remote_id)
                    .first()
                )

            if model:
                ModelMapper.catalog_to_model(entity, model)
            else:
                model = ModelMapper.catalog_to_model(entity)
                session.add(model)

            session.commit()
            session.refresh(model)
            return ModelMapper.catalog_to_entity(model)

    def save_batch(self, entities: list[CatalogModEntity]) -> int:
        if not entities:
            return 0
        saved_count = 0
        with self.db_manager.get_session() as session:
            for ent in entities:
                model = (
                    session.query(CatalogMod)
                    .filter(CatalogMod.source == ent.source, CatalogMod.remote_id == ent.remote_id)
                    .first()
                )
                if model:
                    ModelMapper.catalog_to_model(ent, model)
                else:
                    model = ModelMapper.catalog_to_model(ent)
                    session.add(model)
                saved_count += 1
            session.commit()
        return saved_count

    def update_requirements_overrides(self, mod_id: int, overrides: dict[str, str]) -> bool:
        with self.db_manager.get_session() as session:
            model = session.query(CatalogMod).filter(CatalogMod.id == mod_id).first()
            if not model:
                return False
            existing = model.get_requirements_overrides()
            existing.update(overrides)
            model.set_requirements_overrides(existing)
            session.commit()
            return True

    def get_categories(self) -> list[str]:
        with self.db_manager.get_session() as session:
            results = (
                session.query(distinct(CatalogMod.category))
                .filter(CatalogMod.category.isnot(None), CatalogMod.category != "")
                .all()
            )
            return sorted([r[0] for r in results if r[0]])

    def count(self) -> int:
        with self.db_manager.get_session() as session:
            return session.query(CatalogMod).count()
