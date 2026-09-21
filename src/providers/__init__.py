from typing import Dict, List, Optional
from src.providers.base import BaseSourceProvider
from src.providers.loverslab import LoversLabProvider
from src.providers.patreon import PatreonProvider


class ProviderRegistry:
    """Registry holding all available source providers."""

    _providers: Dict[str, BaseSourceProvider] = {}

    @classmethod
    def initialize(cls) -> None:
        """Exécute l'opération initialize.

        Returns:
            Résultat de l'opération initialize.
        """
        cls._providers["loverslab"] = LoversLabProvider()
        cls._providers["patreon"] = PatreonProvider()

    @classmethod
    def get_provider(cls, name: str) -> Optional[BaseSourceProvider]:
        """Exécute l'opération get provider.

        Args:
            name: Paramètre name.

        Returns:
            Résultat de l'opération get_provider.
        """
        if not cls._providers:
            cls.initialize()
        return cls._providers.get(name.lower())

    @classmethod
    def list_providers(cls) -> List[BaseSourceProvider]:
        """Exécute l'opération list providers.

        Returns:
            Résultat de l'opération list_providers.
        """
        if not cls._providers:
            cls.initialize()
        return list(cls._providers.values())


__all__ = ["BaseSourceProvider", "LoversLabProvider", "PatreonProvider", "ProviderRegistry"]
