"""Service de détection et résolution des mises à jour des mods."""

from __future__ import annotations

from typing import Optional, Union

from src.database.models import CatalogMod, InstalledMod
from src.domain.interfaces.repositories.catalog_repository_interface import ICatalogRepository
from src.domain.interfaces.repositories.mod_repository_interface import IInstalledModRepository
from src.domain.models.mod_entity import CatalogModEntity, InstalledModEntity
from src.infrastructure.database.repositories.sqlalchemy_catalog_repository import (
    SqlAlchemyCatalogRepository,
)
from src.infrastructure.database.repositories.sqlalchemy_installed_mod_repository import (
    SqlAlchemyInstalledModRepository,
)


class ModUpdateService:
    """Service gérant la détection de versions obsolètes et la résolution de catalogue."""

    def __init__(
        self,
        installed_repo: Optional[IInstalledModRepository] = None,
        catalog_repo: Optional[ICatalogRepository] = None,
    ) -> None:
        self._installed_repo = installed_repo or SqlAlchemyInstalledModRepository()
        self._catalog_repo = catalog_repo or SqlAlchemyCatalogRepository()

    def check_update_available(
        self,
        installed_mod: Union[InstalledMod, InstalledModEntity],
        catalog_mod: Optional[Union[CatalogMod, CatalogModEntity]],
    ) -> bool:
        """Détermine si une version plus récente d'un mod est disponible dans le catalogue."""
        if not catalog_mod:
            return False

        updated_date = getattr(catalog_mod, "updated_date", None)
        version_date = getattr(installed_mod, "version_date", None)
        version_str = getattr(catalog_mod, "version_str", "") or ""
        installed_version_str = getattr(installed_mod, "version_str", "") or ""

        # 1. Comparaison des horodatages
        if updated_date and version_date:
            if updated_date > version_date:
                return True

        # 2. Comparaison des chaînes de version si présentes
        if version_str and installed_version_str:
            if version_str.strip() != installed_version_str.strip():
                return True

        # 3. Le catalogue a une date mais le mod installé n'a pas d'horodatage connu
        if not version_date and updated_date:
            return True

        return False

    def resolve_catalog_entry(self, installed_mod: InstalledModEntity) -> Optional[CatalogModEntity]:
        """Résout l'entrée catalogue associée à un mod installé via l'API interne des Repositories."""
        cat_mod: Optional[CatalogModEntity] = None

        if installed_mod.remote_id and installed_mod.source:
            cat_mod = self._catalog_repo.get_by_source_and_remote_id(
                source=installed_mod.source,
                remote_id=installed_mod.remote_id,
            )
            if cat_mod and installed_mod.catalog_mod_id != cat_mod.id:
                installed_mod.catalog_mod_id = cat_mod.id
                self._installed_repo.save(installed_mod)

        if not cat_mod and installed_mod.catalog_mod_id:
            candidate = self._catalog_repo.get_by_id(installed_mod.catalog_mod_id)
            if candidate:
                if installed_mod.remote_id and (
                    candidate.remote_id != installed_mod.remote_id or candidate.source != installed_mod.source
                ):
                    installed_mod.catalog_mod_id = None
                    self._installed_repo.save(installed_mod)
                else:
                    cat_mod = candidate

        return cat_mod


_default_update_service = ModUpdateService()


def check_has_update(
    installed_mod: Union[InstalledMod, InstalledModEntity],
    catalog_mod: Optional[Union[CatalogMod, CatalogModEntity]],
) -> bool:
    """Fonction globale conservée pour compatibilité ascendante."""
    return _default_update_service.check_update_available(installed_mod, catalog_mod)


def resolve_catalog_mod(session, installed_mod: InstalledMod) -> Optional[CatalogMod]:
    """Résout le CatalogMod (compatibilité SQLAlchemy session existante)."""
    cat_mod = None
    if installed_mod.remote_id and installed_mod.source:
        cat_mod = (
            session.query(CatalogMod).filter_by(source=installed_mod.source, remote_id=installed_mod.remote_id).first()
        )
        if cat_mod and installed_mod.catalog_mod_id != cat_mod.id:
            installed_mod.catalog_mod_id = cat_mod.id
            session.commit()

    if not cat_mod and installed_mod.catalog_mod_id:
        candidate = session.query(CatalogMod).filter_by(id=installed_mod.catalog_mod_id).first()
        if candidate:
            if installed_mod.remote_id and (
                candidate.remote_id != installed_mod.remote_id or candidate.source != installed_mod.source
            ):
                installed_mod.catalog_mod_id = None
                session.commit()
            else:
                cat_mod = candidate

    return cat_mod
