"""Entités du domaine Mod (Catalog et Installé)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class CatalogModEntity:
    """Entité métier pure représentant un mod dans le catalogue distant."""

    id: Optional[int] = None
    source: str = "loverslab"
    remote_id: str = ""
    title: str = ""
    author: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    description: str = ""
    page_url: str = ""
    thumbnail_url: str = ""
    download_urls: list[dict[str, Any]] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)
    published_date: Optional[datetime] = None
    updated_date: Optional[datetime] = None
    version_str: str = ""
    patreon_status: str = "NONE"
    patreon_tier: str = ""
    requirements_text: Optional[str] = None
    requirements_status: str = "NONE"
    requirements_mods_json: list[dict[str, Any]] = field(default_factory=list)
    requirements_overrides_json: dict[str, str] = field(default_factory=dict)
    last_scraped_at: Optional[datetime] = None


@dataclass
class InstalledModEntity:
    """Entité métier pure représentant un mod installé dans le dossier Sims 4."""

    id: Optional[int] = None
    catalog_mod_id: Optional[int] = None
    source: str = "manual"
    remote_id: str = ""
    title: str = ""
    folder_name: str = ""
    installed_files: list[str] = field(default_factory=list)
    installed_date: Optional[datetime] = None
    version_date: Optional[datetime] = None
    version_str: str = ""
    is_enabled: bool = True
    backup_path: Optional[str] = None
    catalog_mod: Optional[CatalogModEntity] = None
