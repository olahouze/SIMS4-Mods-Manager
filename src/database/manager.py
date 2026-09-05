import re
import threading
import urllib.parse
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.connection import create_db_engine, get_session_factory, init_db_schema
from src.database.models import CatalogMod, InstalledMod
from src.utils.logger import logger


class DatabaseManager:
    """Gestionnaire principal de la base de données SQLite via SQLAlchemy."""

    _instance: Optional["DatabaseManager"] = None
    _instance_lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None):
        self.engine = create_db_engine(db_path)
        init_db_schema(self.engine)
        self.SessionLocal = get_session_factory(self.engine)
        self.clean_and_repair_catalog()
        logger.info(f"Database initialized at: {db_path or self.engine.url}")

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
            # Auto-migrate catalog_mods schema if columns are missing
            with self.engine.connect() as conn:
                res = conn.execute(text("PRAGMA table_info(catalog_mods)")).fetchall()
                col_names = {r[1] for r in res}
                if "requirements_text" not in col_names:
                    conn.execute(text("ALTER TABLE catalog_mods ADD COLUMN requirements_text TEXT"))
                if "requirements_status" not in col_names:
                    conn.execute(text("ALTER TABLE catalog_mods ADD COLUMN requirements_status VARCHAR(50) DEFAULT 'NONE'"))
                if "requirements_mods_json" not in col_names:
                    conn.execute(text("ALTER TABLE catalog_mods ADD COLUMN requirements_mods_json TEXT DEFAULT '[]'"))
                conn.commit()

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

    def get_catalog_mods_count(self) -> int:
        """Returns the total number of mods currently indexed in the catalog database."""
        try:
            with self.get_session() as session:
                return session.query(CatalogMod).count()
        except Exception:
            return 0
