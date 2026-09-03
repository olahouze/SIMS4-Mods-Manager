from typing import Dict, List, Optional
from src.providers.base import BaseSourceProvider
from src.providers.loverslab import LoversLabProvider
from src.providers.patreon import PatreonProvider

class ProviderRegistry:
    """Registry holding all available source providers."""
    
    _providers: Dict[str, BaseSourceProvider] = {}

    @classmethod
    def initialize(cls) -> None:
        cls._providers["loverslab"] = LoversLabProvider()
        cls._providers["patreon"] = PatreonProvider()

    @classmethod
    def get_provider(cls, name: str) -> Optional[BaseSourceProvider]:
        if not cls._providers:
            cls.initialize()
        return cls._providers.get(name.lower())

    @classmethod
    def list_providers(cls) -> List[BaseSourceProvider]:
        if not cls._providers:
            cls.initialize()
        return list(cls._providers.values())

__all__ = ["BaseSourceProvider", "LoversLabProvider", "PatreonProvider", "ProviderRegistry"]
