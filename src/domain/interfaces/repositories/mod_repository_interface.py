"""Contrat d'API Interne pour le repository des mods installés."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.domain.models.mod_entity import InstalledModEntity


class IInstalledModRepository(ABC):
    """Interface abstraite définissant l'API interne d'accès aux données des mods installés."""

    @abstractmethod
    def get_by_id(self, mod_id: int) -> Optional[InstalledModEntity]:
        """Récupère un mod installé par son ID unique."""
        ...

    @abstractmethod
    def get_by_folder_name(self, folder_name: str) -> Optional[InstalledModEntity]:
        """Récupère un mod installé par le nom de son dossier local."""
        ...

    @abstractmethod
    def get_by_source_and_remote_id(self, source: str, remote_id: str) -> Optional[InstalledModEntity]:
        """Récupère un mod installé par sa provenance et son ID distant."""
        ...

    @abstractmethod
    def get_all(self, enabled_only: Optional[bool] = None) -> list[InstalledModEntity]:
        """Liste tous les mods installés avec filtre optionnel sur leur activation."""
        ...

    @abstractmethod
    def save(self, entity: InstalledModEntity) -> InstalledModEntity:
        """Crée ou met à jour un mod installé."""
        ...

    @abstractmethod
    def delete_by_id(self, mod_id: int) -> bool:
        """Supprime un enregistrement de mod installé par son ID."""
        ...

    @abstractmethod
    def set_enabled(self, mod_id: int, is_enabled: bool) -> bool:
        """Active ou désactive l'état d'un mod installé."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Retourne le nombre total de mods installés."""
        ...
