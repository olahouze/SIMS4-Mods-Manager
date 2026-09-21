"""Contrat d'API Interne pour le repository du catalogue distant."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.domain.models.mod_entity import CatalogModEntity


class ICatalogRepository(ABC):
    """Interface abstraite définissant l'API interne d'accès au catalogue distant."""

    @abstractmethod
    def get_by_id(self, mod_id: int) -> Optional[CatalogModEntity]:
        """Récupère un mod du catalogue par son identifiant unique."""
        ...

    @abstractmethod
    def get_by_source_and_remote_id(self, source: str, remote_id: str) -> Optional[CatalogModEntity]:
        """Récupère un mod du catalogue par sa source et son ID distant."""
        ...

    @abstractmethod
    def search(
        self,
        query: str = "",
        category: str = "",
        author: str = "",
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "updated_date",
        sort_order: str = "desc",
    ) -> tuple[list[CatalogModEntity], int]:
        """Recherche paginée dans le catalogue avec filtres et comptage total."""
        ...

    @abstractmethod
    def get_all(self, limit: Optional[int] = None, offset: int = 0) -> list[CatalogModEntity]:
        """Retourne la liste des mods du catalogue."""
        ...

    @abstractmethod
    def save(self, entity: CatalogModEntity) -> CatalogModEntity:
        """Sauvegarde ou met à jour une entrée du catalogue."""
        ...

    @abstractmethod
    def save_batch(self, entities: list[CatalogModEntity]) -> int:
        """Sauvegarde un lot d'entrées du catalogue en une seule transaction."""
        ...

    @abstractmethod
    def update_requirements_overrides(self, mod_id: int, overrides: dict[str, str]) -> bool:
        """Met à jour les classifications manuelles de dépendances pour un mod."""
        ...

    @abstractmethod
    def get_categories(self) -> list[str]:
        """Liste l'ensemble des catégories distinctes disponibles dans le catalogue."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Retourne le nombre total de mods dans le catalogue."""
        ...
