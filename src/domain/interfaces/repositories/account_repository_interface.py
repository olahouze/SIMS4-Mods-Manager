"""Contrat d'API Interne pour la gestion des sessions d'authentification."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.domain.models.account_entity import AccountSessionEntity


class IAccountRepository(ABC):
    """Interface abstraite définissant l'API interne d'accès aux sessions de providers."""

    @abstractmethod
    def get_by_provider(self, provider_name: str) -> Optional[AccountSessionEntity]:
        """Récupère la session d'un provider donné."""
        ...

    @abstractmethod
    def get_all(self) -> list[AccountSessionEntity]:
        """Liste toutes les sessions de providers enregistrées."""
        ...

    @abstractmethod
    def save(self, entity: AccountSessionEntity) -> AccountSessionEntity:
        """Sauvegarde ou met à jour la session d'un provider."""
        ...

    @abstractmethod
    def delete(self, provider_name: str) -> bool:
        """Supprime la session d'un provider."""
        ...
