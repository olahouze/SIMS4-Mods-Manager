"""Service de basculement d'état (activation / désactivation) des mods installés."""

from __future__ import annotations

from typing import Optional

from src.core.config import AppConfig
from src.domain.interfaces.repositories.mod_repository_interface import IInstalledModRepository
from src.infrastructure.database.repositories.sqlalchemy_installed_mod_repository import (
    SqlAlchemyInstalledModRepository,
)
from src.application.game.game_service import GameDetector
from src.utils.logger import logger


class ModToggleManager:
    """Gère l'activation et la désactivation des mods sans suppression de fichiers."""

    def __init__(self, mod_repository: Optional[IInstalledModRepository] = None) -> None:
        self._repo = mod_repository

    @property
    def repo(self) -> IInstalledModRepository:
        """Exécute l'opération repo.

        Returns:
            Résultat de l'opération repo.
        """
        return self._repo or SqlAlchemyInstalledModRepository()

    def toggle(self, installed_mod_id: int, target_state: Optional[bool] = None) -> tuple[bool, str]:
        """Bascule l'état activé/désactivé d'un mod installé via l'API interne du Repository."""
        mod = self.repo.get_by_id(installed_mod_id)
        if not mod:
            return False, f"Mod with ID {installed_mod_id} not found."

        new_state = (not mod.is_enabled) if target_state is None else target_state
        if mod.is_enabled == new_state:
            return True, f"Mod '{mod.title}' is already {'enabled' if new_state else 'disabled'}."

        mods_dir = GameDetector.detect_mods_dir(AppConfig.load().custom_mods_dir)
        if not mods_dir or not mods_dir.exists():
            return False, "Sims 4 Mods folder could not be found."

        mod_folder = mods_dir / mod.folder_name
        if not mod_folder.exists():
            return False, f"Mod folder '{mod.folder_name}' does not exist on disk."

        updated_files: list[str] = []
        for file_path in mod_folder.rglob("*"):
            if not file_path.is_file():
                continue

            rel_path = file_path.relative_to(mods_dir)

            if not new_state:
                # Désactivation : renommage en .disabled
                if file_path.suffix.lower() in [".package", ".ts4script"]:
                    new_file_path = file_path.with_name(file_path.name + ".disabled")
                    file_path.rename(new_file_path)
                    updated_files.append(str(new_file_path.relative_to(mods_dir)))
                else:
                    updated_files.append(str(rel_path))
            else:
                # Activation : retrait de .disabled
                if file_path.name.lower().endswith(".package.disabled"):
                    new_file_path = file_path.with_name(file_path.name[:-9])
                    file_path.rename(new_file_path)
                    updated_files.append(str(new_file_path.relative_to(mods_dir)))
                elif file_path.name.lower().endswith(".ts4script.disabled"):
                    new_file_path = file_path.with_name(file_path.name[:-9])
                    file_path.rename(new_file_path)
                    updated_files.append(str(new_file_path.relative_to(mods_dir)))
                else:
                    updated_files.append(str(rel_path))

        mod.is_enabled = new_state
        mod.installed_files = updated_files
        self.repo.save(mod)

        status_str = "activé" if new_state else "désactivé"
        logger.info(f"Mod '{mod.title}' {status_str} avec succès.")
        return True, f"Mod '{mod.title}' {status_str}."

    @classmethod
    def toggle_mod(cls, installed_mod_id: int, target_state: Optional[bool] = None) -> tuple[bool, str]:
        """Méthode de classe conservée pour compatibilité ascendante."""
        return cls().toggle(installed_mod_id, target_state)


ModToggleService = ModToggleManager
