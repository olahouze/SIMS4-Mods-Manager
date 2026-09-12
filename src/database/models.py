import json
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    JSON,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class CatalogMod(Base):
    """Représente un mod répertorié dans le catalogue distant (LoversLab, Patreon...)."""

    __tablename__ = "catalog_mods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False, index=True)  # e.g., 'loverslab', 'patreon'
    remote_id = Column(String(100), nullable=False, index=True)  # ID sur le site distant
    title = Column(String(255), nullable=False, index=True)
    author = Column(String(100), index=True)
    category = Column(String(100), index=True)
    tags = Column(JSON, default=list)  # JSON list of tags
    description = Column(Text, default="")
    page_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), default="")
    download_urls = Column(JSON, default=list)  # JSON list of direct download URLs
    external_links = Column(JSON, default=list)  # JSON list of external links (Patreon, Mega, etc.)
    published_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True, index=True)
    version_str = Column(String(50), default="")
    patreon_status = Column(String(20), default="NONE", index=True)  # NONE, PUBLIC, UNLOCKED, LOCKED, UNKNOWN
    patreon_tier = Column(String(100), default="")
    requirements_text = Column(Text, nullable=True)
    requirements_status = Column(String(50), default="NONE")  # NONE, RESOLVED, PENDING_VERIFICATION
    requirements_mods_json = Column(JSON, default=list)  # JSON list of resolved LoversLab dependencies
    last_scraped_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_source_remote", "source", "remote_id", unique=True),
        Index("idx_source_updated", "source", "updated_date"),
        Index("idx_source_title", "source", "title"),
    )

    def get_tags_list(self) -> List[str]:
        if isinstance(self.tags, list):
            return self.tags
        try:
            return json.loads(self.tags or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    def set_tags_list(self, tags_list: List[str]) -> None:
        self.tags = list(tags_list) if tags_list is not None else []

    def get_download_urls_list(self) -> List[Dict[str, Any]]:
        if isinstance(self.download_urls, list):
            return self.download_urls
        try:
            return json.loads(self.download_urls or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    def set_download_urls_list(self, urls: List[Dict[str, Any]]) -> None:
        self.download_urls = list(urls) if urls is not None else []

    def get_external_links_list(self) -> List[str]:
        if isinstance(self.external_links, list):
            return self.external_links
        try:
            return json.loads(self.external_links or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    def set_external_links_list(self, links: List[str]) -> None:
        self.external_links = list(links) if links is not None else []

    def get_requirements_mods_list(self) -> List[Dict[str, Any]]:
        if isinstance(self.requirements_mods_json, list):
            return self.requirements_mods_json
        try:
            return json.loads(self.requirements_mods_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    def set_requirements_mods_list(self, reqs: List[Dict[str, Any]]) -> None:
        self.requirements_mods_json = list(reqs) if reqs is not None else []


class InstalledMod(Base):
    """Représente un mod installé localement dans le dossier Mods des Sims 4."""

    __tablename__ = "installed_mods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    catalog_mod_id = Column(Integer, ForeignKey("catalog_mods.id", ondelete="SET NULL"), nullable=True)
    source = Column(String(50), default="manual")
    remote_id = Column(String(100), default="")
    title = Column(String(255), nullable=False, index=True)
    folder_name = Column(String(255), nullable=False, index=True)
    installed_files = Column(JSON, default=list)  # JSON list of relative file paths
    installed_date = Column(DateTime, default=datetime.now)
    version_date = Column(DateTime, nullable=True)
    version_str = Column(String(50), default="")
    is_enabled = Column(Boolean, default=True, index=True)
    backup_path = Column(String(500), nullable=True)

    catalog_mod = relationship("CatalogMod", backref="installed_mod", uselist=False)

    def get_installed_files_list(self) -> List[str]:
        if isinstance(self.installed_files, list):
            return self.installed_files
        try:
            return json.loads(self.installed_files or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    def set_installed_files_list(self, files: List[str]) -> None:
        self.installed_files = list(files) if files is not None else []


class AccountSession(Base):
    """Stocke la session de connexion et cookies pour un provider (LoversLab, Patreon)."""

    __tablename__ = "account_sessions"

    provider_name = Column(String(50), primary_key=True)  # 'loverslab', 'patreon'
    is_authenticated = Column(Boolean, default=False)
    user_display_name = Column(String(100), default="")
    cookies_data = Column(JSON, default=dict)  # JSON dict of cookies
    user_agent = Column(String(255), default="")
    last_verified = Column(DateTime, default=datetime.now)

    def get_cookies_dict(self) -> Dict[str, str]:
        if isinstance(self.cookies_data, dict):
            return self.cookies_data
        try:
            return json.loads(self.cookies_data or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_cookies_dict(self, cookies: Dict[str, str]) -> None:
        self.cookies_data = dict(cookies) if cookies is not None else {}
