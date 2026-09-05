from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class ModDetailsDTO:
    """Représente les métadonnées complètes d'un mod extraites par un provider."""

    remote_id: str
    title: str
    page_url: str
    source: str = "loverslab"
    author: str = ""
    category: str = ""
    description: str = ""
    thumbnail_url: str = ""
    version_str: str = ""
    published_date: Optional[datetime] = None
    updated_date: Optional[datetime] = None
    download_urls: List[Dict[str, Any]] = field(default_factory=list)
    external_links: List[str] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    requirements_text: Optional[str] = None
    requirements_status: str = "NONE"
    requirements_mods: List[Dict[str, Any]] = field(default_factory=list)
    patreon_status: str = "NONE"
    patreon_tier: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convertit le DTO en dictionnaire pour la sérialisation API et l'interopérabilité."""
        res = asdict(self)
        if self.published_date:
            res["published_date"] = self.published_date.isoformat()
        if self.updated_date:
            res["updated_date"] = self.updated_date.isoformat()
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModDetailsDTO":
        """Instancie un ModDetailsDTO depuis un dictionnaire brut."""
        valid_fields = {k for k in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


@dataclass
class DownloadResultDTO:
    """Résultat standardisé d'un téléchargement de mod."""

    success: bool
    message: str
    file_path: Optional[str] = None
    file_size_bytes: int = 0
