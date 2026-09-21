"""Service applicatif pour la gestion des mods installés."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

from src.api.schemas.installed import (
    InstalledListResponse,
    InstalledModItem,
    InstalledOpenFolderResponse,
    InstalledScanResponse,
    InstalledToggleResponse,
    InstalledUninstallResponse,
    ModDependentItem,
    ModDependentsResponse,
)
from src.core.config import AppConfig
from src.database.manager import DatabaseManager
from src.database.models import InstalledMod
from src.domain.interfaces.repositories.catalog_repository_interface import ICatalogRepository
from src.domain.interfaces.repositories.mod_repository_interface import IInstalledModRepository
from src.infrastructure.database.repositories.sqlalchemy_catalog_repository import (
    SqlAlchemyCatalogRepository,
)
from src.infrastructure.database.repositories.sqlalchemy_installed_mod_repository import (
    SqlAlchemyInstalledModRepository,
)
from src.application.dependencies.dependency_resolver import find_dependent_installed_mods
from src.application.game.game_service import GameDetector
from src.application.mods.mod_installer_service import ModInstaller
from src.application.mods.mod_toggle_service import ModToggleManager
from src.application.mods.mod_update_service import ModUpdateService


class InstalledModsService:
    """Service d'orchestration pour les opérations sur les mods installés."""

    def __init__(
        self,
        installed_repo: Optional[IInstalledModRepository] = None,
        catalog_repo: Optional[ICatalogRepository] = None,
        update_service: Optional[ModUpdateService] = None,
        toggle_manager: Optional[ModToggleManager] = None,
    ) -> None:
        self._installed_repo = installed_repo
        self._catalog_repo = catalog_repo
        self._update_service = update_service
        self._toggle_manager = toggle_manager

    @property
    def installed_repo(self) -> IInstalledModRepository:
        """Exécute l'opération installed repo.

        Returns:
            Résultat de l'opération installed_repo.
        """
        return self._installed_repo or SqlAlchemyInstalledModRepository()

    @property
    def catalog_repo(self) -> ICatalogRepository:
        """Exécute l'opération catalog repo.

        Returns:
            Résultat de l'opération catalog_repo.
        """
        return self._catalog_repo or SqlAlchemyCatalogRepository()

    @property
    def update_service(self) -> ModUpdateService:
        """Exécute l'opération update service.

        Returns:
            Résultat de l'opération update_service.
        """
        return self._update_service or ModUpdateService(self.installed_repo, self.catalog_repo)

    @property
    def toggle_manager(self) -> ModToggleManager:
        """Exécute l'opération toggle manager.

        Returns:
            Résultat de l'opération toggle_manager.
        """
        return self._toggle_manager or ModToggleManager(self.installed_repo)

    def list_installed_mods(self, search: Optional[str] = None) -> InstalledListResponse:
        """Liste les mods installés avec détection des mises à jour et statistiques."""
        all_mods = self.installed_repo.get_all()

        if search:
            s_clean = search.strip().lower()
            all_mods = [m for m in all_mods if s_clean in m.title.lower() or s_clean in m.folder_name.lower()]

        all_catalog = self.catalog_repo.get_all()
        catalog_by_id = {cm.id: cm for cm in all_catalog if cm.id is not None}
        catalog_by_key = {(cm.source, cm.remote_id): cm for cm in all_catalog if cm.remote_id}

        items: list[InstalledModItem] = []
        enabled_count = 0
        disabled_count = 0

        for m in all_mods:
            if m.is_enabled:
                enabled_count += 1
            else:
                disabled_count += 1

            cat_mod = None
            if m.catalog_mod_id and m.catalog_mod_id in catalog_by_id:
                cat_mod = catalog_by_id[m.catalog_mod_id]
            elif m.remote_id and m.source and (m.source, m.remote_id) in catalog_by_key:
                cat_mod = catalog_by_key[(m.source, m.remote_id)]

            has_update = self.update_service.check_update_available(m, cat_mod)

            items.append(
                InstalledModItem(
                    id=m.id or 0,
                    catalog_mod_id=m.catalog_mod_id,
                    source=m.source,
                    remote_id=m.remote_id,
                    title=m.title,
                    author=cat_mod.author if cat_mod else "",
                    folder_name=m.folder_name,
                    thumbnail_url=cat_mod.thumbnail_url if cat_mod else "",
                    page_url=cat_mod.page_url if cat_mod else "",
                    requirements_text=cat_mod.requirements_text if cat_mod else None,
                    requirements_status=cat_mod.requirements_status if cat_mod else "NONE",
                    dependencies=[],
                    screenshots=[],
                    is_enabled=m.is_enabled,
                    installed_date=m.installed_date,
                    version_date=m.version_date,
                    version_str=m.version_str,
                    files_count=len(m.installed_files),
                    files_list=m.installed_files,
                    backup_path=m.backup_path,
                    has_update=has_update,
                )
            )

        return InstalledListResponse(
            total=len(items),
            enabled_count=enabled_count,
            disabled_count=disabled_count,
            items=items,
        )

    def toggle_mod(self, mod_id: int, target_state: Optional[bool] = None) -> InstalledToggleResponse:
        """Active ou désactive un mod."""
        success, message = self.toggle_manager.toggle(mod_id, target_state)
        mod = self.installed_repo.get_by_id(mod_id)
        is_enabled = mod.is_enabled if mod else False
        return InstalledToggleResponse(
            success=success,
            message=message,
            is_enabled=is_enabled,
        )

    def uninstall_mod(self, mod_id: int) -> InstalledUninstallResponse:
        """Désinstalle un mod du disque et de la base de données."""
        success, message = ModInstaller.uninstall_mod(mod_id)
        return InstalledUninstallResponse(success=success, message=message)

    def scan_mods(self) -> InstalledScanResponse:
        """Scanne le répertoire Mods pour détecter les ajouts ou suppressions manuelles."""
        results = ModInstaller.scan_existing_mods()
        return InstalledScanResponse(
            success=True,
            message=f"{len(results)} mod(s) scanné(s) ou mis à jour.",
            count=len(results),
            found=results,
        )

    def get_dependents(self, mod_id: int) -> ModDependentsResponse:
        """Recherche les mods installés dépendant du mod spécifié."""
        with DatabaseManager.get_instance().get_session() as session:
            target = session.query(InstalledMod).filter_by(id=mod_id).first()
            if not target:
                return ModDependentsResponse(
                    mod_id=mod_id,
                    mod_title="",
                    has_dependents=False,
                    count=0,
                    dependents=[],
                )
            dependents = find_dependent_installed_mods(mod_id, session)

            items = [
                ModDependentItem(
                    id=d["id"],
                    title=d["title"],
                    folder_name=d["folder_name"],
                )
                for d in dependents
            ]

            return ModDependentsResponse(
                mod_id=mod_id,
                mod_title=target.title or "",
                has_dependents=len(items) > 0,
                count=len(items),
                dependents=items,
            )

    def open_mod_folder(self, folder_name: Optional[str] = None) -> InstalledOpenFolderResponse:
        """Ouvre le dossier d'un mod dans l'explorateur de fichiers."""
        mods_dir = GameDetector.detect_mods_dir(AppConfig.load().custom_mods_dir)
        if not mods_dir or not mods_dir.exists():
            return InstalledOpenFolderResponse(success=False, message="Dossier Mods de Sims 4 introuvable.")

        target_path = mods_dir
        if folder_name:
            target_path = mods_dir / folder_name
            if not target_path.exists():
                return InstalledOpenFolderResponse(success=False, message=f"Sous-dossier '{folder_name}' introuvable.")

        try:
            if os.name == "nt":
                os.startfile(str(target_path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target_path)])
            else:
                subprocess.Popen(["xdg-open", str(target_path)])
            return InstalledOpenFolderResponse(success=True, message=f"Dossier ouvert: {target_path}")
        except Exception as e:
            return InstalledOpenFolderResponse(success=False, message=f"Impossible d'ouvrir le dossier: {e}")
