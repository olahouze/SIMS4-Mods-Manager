from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional, Callable, Union
from pathlib import Path

from src.core.dto import ModDetailsDTO


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
    def get_mod_details(self, mod_url: str) -> Union[Dict[str, Any], ModDetailsDTO]:
        """
        Fetches full details for a specific mod page (download links, external links, version).
        """
        pass

    @abstractmethod
    def download_mod_file(
        self,
        download_url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
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

    @abstractmethod
    def check_user_already_commented(
        self, page_url: str, required_keywords: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Checks live on the provider's site/forum if the authenticated user has already
        posted a comment/message containing the given keywords.
        Returns (already_commented, formatted_datetime_or_snippet).
        """
        pass

    @abstractmethod
    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        """
        Posts a comment or message on the mod page/forum using the authenticated member session.
        Returns (success, message_or_error).
        """
        pass

