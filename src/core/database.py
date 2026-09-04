import json
import re
import threading
import urllib.parse
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from src.core.config import AppConfig
from src.utils.logger import logger

Base = declarative_base()


class CatalogMod(Base):
    __tablename__ = "catalog_mods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False, index=True)  # e.g., 'loverslab', 'patreon'
    remote_id = Column(String(100), nullable=False, index=True)  # ID on the remote site
    title = Column(String(255), nullable=False, index=True)
    author = Column(String(100), index=True)
    category = Column(String(100), index=True)
    tags = Column(Text, default="[]")  # JSON list of tags
    description = Column(Text, default="")
    page_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), default="")
    download_urls = Column(Text, default="[]")  # JSON list of direct download URLs
    external_links = Column(Text, default="[]")  # JSON list of external links (Patreon, Mega, etc.)
    published_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True, index=True)
    version_str = Column(String(50), default="")
    patreon_status = Column(String(20), default="NONE", index=True)  # NONE, PUBLIC, UNLOCKED, LOCKED, UNKNOWN
    patreon_tier = Column(String(100), default="")
    # Note: datetime.now without () is intentional — SQLAlchemy calls it as a factory at insert time
    last_scraped_at = Column(DateTime, default=datetime.now)

    __table_args__ = (Index("idx_source_remote", "source", "remote_id", unique=True),)

    def get_tags_list(self) -> List[str]:
        try:
            return json.loads(self.tags or "[]")
        except Exception:
            return []

    def set_tags_list(self, tags_list: List[str]) -> None:
        self.tags = json.dumps(tags_list, ensure_ascii=False)

    def get_download_urls_list(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.download_urls or "[]")
        except Exception:
            return []

    def set_download_urls_list(self, urls: List[Dict[str, Any]]) -> None:
        self.download_urls = json.dumps(urls, ensure_ascii=False)

    def get_external_links_list(self) -> List[str]:
        try:
            return json.loads(self.external_links or "[]")
        except Exception:
            return []

    def set_external_links_list(self, links: List[str]) -> None:
        self.external_links = json.dumps(links, ensure_ascii=False)


class InstalledMod(Base):
    __tablename__ = "installed_mods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    catalog_mod_id = Column(Integer, ForeignKey("catalog_mods.id", ondelete="SET NULL"), nullable=True)
    source = Column(String(50), default="manual")
    remote_id = Column(String(100), default="")
    title = Column(String(255), nullable=False, index=True)
    folder_name = Column(String(255), nullable=False, index=True)
    installed_files = Column(Text, default="[]")  # JSON list of relative file paths
    installed_date = Column(DateTime, default=datetime.now)
    version_date = Column(DateTime, nullable=True)
    version_str = Column(String(50), default="")
    is_enabled = Column(Boolean, default=True, index=True)
    backup_path = Column(String(500), nullable=True)

    catalog_mod = relationship("CatalogMod", backref="installed_mod", uselist=False)

    def get_installed_files_list(self) -> List[str]:
        try:
            return json.loads(self.installed_files or "[]")
        except Exception:
            return []

    def set_installed_files_list(self, files: List[str]) -> None:
        self.installed_files = json.dumps(files, ensure_ascii=False)


class AccountSession(Base):
    __tablename__ = "account_sessions"

    provider_name = Column(String(50), primary_key=True)  # 'loverslab', 'patreon'
    is_authenticated = Column(Boolean, default=False)
    user_display_name = Column(String(100), default="")
    cookies_data = Column(Text, default="{}")  # JSON dict of cookies
    user_agent = Column(String(255), default="")
    last_verified = Column(DateTime, default=datetime.now)

    def get_cookies_dict(self) -> Dict[str, str]:
        try:
            return json.loads(self.cookies_data or "{}")
        except Exception:
            return {}

    def set_cookies_dict(self, cookies: Dict[str, str]) -> None:
        self.cookies_data = json.dumps(cookies, ensure_ascii=False)


class DatabaseManager:
    _instance: Optional["DatabaseManager"] = None
    _instance_lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            db_path = str(AppConfig.get_db_path())
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.clean_and_repair_catalog()
        logger.info(f"Database initialized at: {db_path}")

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> "DatabaseManager":
        """Thread-safe singleton accessor with double-checked locking."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = DatabaseManager(db_path)
        return cls._instance

    def get_session(self) -> Session:
        return self.SessionLocal()

    def clean_and_repair_catalog(self) -> None:
        """
        Repairs corrupted catalog records (empty titles) from page_url slug,
        and purges known deleted ghost mods (such as remote_id 51260 / author dohmra).
        """

        try:
            with self.get_session() as session:
                # 1. Delete ghost mod 51260 / dohmra
                ghosts = (
                    session.query(CatalogMod)
                    .filter((CatalogMod.remote_id == "51260") | (CatalogMod.author == "dohmra"))
                    .all()
                )
                for g in ghosts:
                    logger.info(f"Purge du mod fantôme LoversLab #{g.remote_id} ({g.author})")
                    session.delete(g)

                # 2. Repair empty or corrupt titles
                corrupt_items = (
                    session.query(CatalogMod)
                    .filter(
                        (CatalogMod.title == "")
                        | (CatalogMod.title == "''")
                        | (CatalogMod.title == '""')
                        | (CatalogMod.title == "Mod")
                    )
                    .all()
                )

                repaired_count = 0
                for item in corrupt_items:
                    if item.page_url:
                        slug_match = re.search(r"/files/file/\d+-([^/]+)", urllib.parse.unquote(item.page_url))
                        if slug_match:
                            cleaned_title = (
                                slug_match.group(1)
                                .replace("-", " ")
                                .replace("—", "-")
                                .replace("\u200b", "")
                                .replace("\ufeff", "")
                                .strip()
                                .title()
                            )
                            item.title = cleaned_title
                            repaired_count += 1
                        else:
                            session.delete(item)
                    else:
                        session.delete(item)

                # 3. Disconnect or repair mismatched catalog_mod_id foreign keys in InstalledMod
                installed_mods = session.query(InstalledMod).filter(InstalledMod.catalog_mod_id.isnot(None)).all()
                repaired_links = 0
                for im in installed_mods:
                    cm = session.query(CatalogMod).filter_by(id=im.catalog_mod_id).first()
                    if not cm:
                        # Stale pointer to deleted catalog mod
                        im.catalog_mod_id = None
                        repaired_links += 1
                    elif im.remote_id and (cm.remote_id != im.remote_id or cm.source != im.source):
                        logger.warning(
                            f"Réparation clé étrangère erronée : mod installé '{im.title}' (remote_id={im.remote_id}) "
                            f"était faussement lié au mod catalogue #{cm.id} '{cm.title}' (remote_id={cm.remote_id}). Dissociation."
                        )
                        true_match = session.query(CatalogMod).filter_by(source=im.source, remote_id=im.remote_id).first()
                        im.catalog_mod_id = true_match.id if true_match else None
                        repaired_links += 1

                if ghosts or repaired_count or repaired_links:
                    session.commit()
                    logger.info(
                        f"Maintenance catalogue : {len(ghosts)} fantôme(s), {repaired_count} titre(s) réparé(s), {repaired_links} lien(s) corrigé(s)."
                    )
        except Exception as e:
            logger.debug(f"Erreur maintenance catalogue: {e}")

    def purge_catalog(self) -> int:
        """Purges all records from the catalog_mods table to restart from a clean catalog."""
        try:
            with self.get_session() as session:
                # Disconnect all installed mods from catalog to prevent dangling/mismatched foreign keys
                session.query(InstalledMod).update({InstalledMod.catalog_mod_id: None})
                count = session.query(CatalogMod).delete()
                session.commit()
                logger.info(f"Purge complète du catalogue effectuée : {count} mods supprimés.")
                return count
        except Exception as e:
            logger.error(f"Erreur lors de la purge du catalogue : {e}")
            return 0
