from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from src.core.database import CatalogMod

class BaseSourceProvider(ABC):
    """Abstract base class for mod source providers (LoversLab, Patreon, etc.)."""

    provider_name: str = "base"
    display_name: str = "Base Provider"
    base_url: str = ""

    @abstractmethod
    def scrape_catalog(self, page: int = 1, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Scrapes a page of the mod catalog and returns raw mod metadata dicts.
        """
        pass

    @abstractmethod
    def get_mod_details(self, mod_url: str) -> Dict[str, Any]:
        """
        Fetches full details for a specific mod page (download links, external links, version).
        """
        pass

    @abstractmethod
    def download_mod_file(self, download_url: str, dest_path: Path) -> Tuple[bool, str]:
        """
        Downloads a mod file from a direct or resolved download URL.
        """
        pass

    @abstractmethod
    def check_access(self, mod_data: Dict[str, Any]) -> str:
        """
        Checks accessibility status (e.g. PUBLIC, UNLOCKED, LOCKED).
        """
        pass
