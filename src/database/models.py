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


def _get_json_data(val: Any, default_type: type):
    if isinstance(val, default_type):
        return val
    try:
        return json.loads(val or ("[]" if default_type is list else "{}"))
    except (json.JSONDecodeError, TypeError):
        return default_type()


def _set_json_data(val: Any, default_type: type):
    return default_type(val) if val is not None else default_type()


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
    requirements_overrides_json = Column(
        JSON, default=dict
    )  # JSON dict of user classification {title: "MOD"|"COMMENT"}
    last_scraped_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_source_remote", "source", "remote_id", unique=True),
        Index("idx_source_updated", "source", "updated_date"),
        Index("idx_source_title", "source", "title"),
    )

    def get_tags_list(self) -> List[str]:
        return _get_json_data(self.tags, list)

    def set_tags_list(self, tags_list: List[str]) -> None:
        self.tags = _set_json_data(tags_list, list)

    def get_download_urls_list(self) -> List[Dict[str, Any]]:
        return _get_json_data(self.download_urls, list)

    def set_download_urls_list(self, urls: List[Dict[str, Any]]) -> None:
        self.download_urls = _set_json_data(urls, list)

    def get_external_links_list(self) -> List[str]:
        return _get_json_data(self.external_links, list)

    def set_external_links_list(self, links: List[str]) -> None:
        self.external_links = _set_json_data(links, list)

    def get_requirements_mods_list(self) -> List[Dict[str, Any]]:
        return _get_json_data(self.requirements_mods_json, list)

    def set_requirements_mods_list(self, reqs: List[Dict[str, Any]]) -> None:
        self.requirements_mods_json = _set_json_data(reqs, list)

    def get_requirements_overrides(self) -> Dict[str, str]:
        return _get_json_data(self.requirements_overrides_json, dict)

    def set_requirements_overrides(self, overrides: Dict[str, str]) -> None:
        self.requirements_overrides_json = _set_json_data(overrides, dict)


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

    __table_args__ = (
        Index("idx_installed_source_remote", "source", "remote_id"),
        Index("idx_installed_catalog_id", "catalog_mod_id"),
        Index("idx_installed_folder", "folder_name"),
    )

    def get_installed_files_list(self) -> List[str]:
        return _get_json_data(self.installed_files, list)

    def set_installed_files_list(self, files: List[str]) -> None:
        self.installed_files = _set_json_data(files, list)


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
        return _get_json_data(self.cookies_data, dict)

    def set_cookies_dict(self, cookies: Dict[str, str]) -> None:
        self.cookies_data = _set_json_data(cookies, dict)
