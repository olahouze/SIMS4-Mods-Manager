import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from src.core.config import AppConfig
from src.core.database import DatabaseManager, InstalledMod, CatalogMod
from src.core.game_detector import GameDetector
from src.utils.archive import extract_archive, is_archive, create_backup_zip
from src.utils.logger import logger

def sanitize_filename(name: str) -> str:
    """Sanitizes folder and file names to be valid on Windows."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = clean.strip().replace(" ", "_")
    return clean or "Mod"

class ModInstaller:
    """Handles mod installation, extraction, ts4script depth fixing, backups, uninstallation, and scanning."""

    @classmethod
    def install_mod_from_file(
        cls,
        file_path: Path,
        catalog_mod: Optional[CatalogMod] = None,
        source: str = "manual",
        custom_title: Optional[str] = None,
        version_date: Optional[datetime] = None,
        version_str: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Installs a mod from a downloaded file (archive or direct package/script).
        """
        config = AppConfig.load()
        mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
        if not mods_dir:
            return False, "Dossier Mods de Sims 4 introuvable. Veuillez vérifier vos paramètres."

        title = custom_title or (catalog_mod.title if catalog_mod else file_path.stem)
        source_name = source or (catalog_mod.source if catalog_mod else "manual")
        remote_id = catalog_mod.remote_id if catalog_mod else ""
        catalog_id = catalog_mod.id if catalog_mod else None

        safe_folder_name = f"{sanitize_filename(source_name)}_{sanitize_filename(title)}"
        target_mod_dir = mods_dir / safe_folder_name

        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            existing_installed = session.query(InstalledMod).filter_by(folder_name=safe_folder_name).first()
            if not existing_installed and catalog_id:
                existing_installed = session.query(InstalledMod).filter_by(catalog_mod_id=catalog_id).first()

            backup_file_path = None
            if existing_installed and target_mod_dir.exists():
                # Perform automatic backup if configured
                if config.auto_backup:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"{safe_folder_name}_{timestamp}.zip"
                    backup_dest = AppConfig.get_backups_dir() / backup_name
                    try:
                        create_backup_zip(target_mod_dir, backup_dest)
                        backup_file_path = str(backup_dest)
                        logger.info(f"Backup created at: {backup_dest}")
                    except Exception as e:
                        logger.warning(f"Backup failed: {e}")

                # Clean old folder contents
                shutil.rmtree(target_mod_dir, ignore_errors=True)

            target_mod_dir.mkdir(parents=True, exist_ok=True)
            installed_files: List[str] = []

            # Extract archive or copy single file
            if is_archive(file_path):
                try:
                    extracted = extract_archive(file_path, target_mod_dir)
                    for f in extracted:
                        if f.is_file():
                            installed_files.append(str(f.relative_to(mods_dir)))
                except Exception as e:
                    logger.error(f"Extraction error: {e}")
                    return False, f"Erreur lors de l'extraction de l'archive: {e}"
            else:
                dest_file = target_mod_dir / file_path.name
                shutil.copy2(file_path, dest_file)
                installed_files.append(str(dest_file.relative_to(mods_dir)))

            # CRITICAL SIMS 4 FIX: Ensure all .ts4script are at max 1 level of subfolder
            # i.e., direct children of target_mod_dir
            cls._fix_ts4script_depth(target_mod_dir, mods_dir)

            # Re-index files in folder
            installed_files = [
                str(p.relative_to(mods_dir))
                for p in target_mod_dir.rglob("*")
                if p.is_file()
            ]

            # Update or create DB record
            if not existing_installed:
                installed_record = InstalledMod(
                    catalog_mod_id=catalog_id,
                    source=source_name,
                    remote_id=remote_id,
                    title=title,
                    folder_name=safe_folder_name,
                    installed_date=datetime.now(),
                    version_date=version_date or (catalog_mod.updated_date if catalog_mod else None),
                    version_str=version_str or (catalog_mod.version_str if catalog_mod else ""),
                    is_enabled=True,
                    backup_path=backup_file_path,
                )
                installed_record.set_installed_files_list(installed_files)
                session.add(installed_record)
            else:
                existing_installed.installed_date = datetime.now()
                existing_installed.version_date = version_date or (catalog_mod.updated_date if catalog_mod else existing_installed.version_date)
                existing_installed.version_str = version_str or (catalog_mod.version_str if catalog_mod else existing_installed.version_str)
                existing_installed.catalog_mod_id = catalog_id or existing_installed.catalog_mod_id
                existing_installed.is_enabled = True
                if backup_file_path:
                    existing_installed.backup_path = backup_file_path
                existing_installed.set_installed_files_list(installed_files)

            session.commit()

        logger.info(f"Mod '{title}' successfully installed in {target_mod_dir}")
        return True, f"Mod '{title}' installé avec succès !"

    @classmethod
    def _fix_ts4script_depth(cls, mod_dir: Path, mods_root: Path) -> None:
        """
        Moves any .ts4script files found in deep subfolders directly to mod_dir.
        Sims 4 only loads python scripts if they are at most 1 folder deep from Mods/.
        """
        for script_file in list(mod_dir.rglob("*.ts4script")):
            if script_file.parent != mod_dir:
                dest = mod_dir / script_file.name
                if dest.exists() and dest != script_file:
                    dest = mod_dir / f"{script_file.stem}_{sanitize_filename(script_file.parent.name)}.ts4script"
                logger.info(f"Relocating .ts4script from depth > 1 to: {dest}")
                shutil.move(str(script_file), str(dest))

    @classmethod
    def uninstall_mod(cls, installed_mod_id: int) -> Tuple[bool, str]:
        """Removes the mod folder and its database record."""
        config = AppConfig.load()
        mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
        db = DatabaseManager.get_instance()

        with db.get_session() as session:
            mod = session.query(InstalledMod).filter_by(id=installed_mod_id).first()
            if not mod:
                return False, "Mod introuvable dans la base de données."

            if mods_dir:
                target_dir = mods_dir / mod.folder_name
                if target_dir.exists():
                    try:
                        shutil.rmtree(target_dir)
                        logger.info(f"Removed mod directory: {target_dir}")
                    except Exception as e:
                        logger.error(f"Failed to delete mod folder: {e}")
                        return False, f"Impossible de supprimer le dossier du mod: {e}"

            session.delete(mod)
            session.commit()

        return True, "Mod désinstallé avec succès."

    @classmethod
    def scan_existing_mods(cls) -> List[Dict[str, Any]]:
        """
        Scans the Sims 4 Mods directory for manually placed mods and indexes them.
        """
        config = AppConfig.load()
        mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
        if not mods_dir or not mods_dir.exists():
            return []

        found_mods = []
        db = DatabaseManager.get_instance()

        with db.get_session() as session:
            # 1. Scan subfolders
            for item in mods_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    folder_name = item.name
                    files = [str(p.relative_to(mods_dir)) for p in item.rglob("*") if p.is_file()]
                    if not files:
                        continue

                    # Check if already in DB
                    existing = session.query(InstalledMod).filter_by(folder_name=folder_name).first()
                    is_enabled = not all(f.endswith(".disabled") for f in files)
                    
                    if not existing:
                        # Try to match with catalog mod
                        matched_cat = session.query(CatalogMod).filter(
                            CatalogMod.title.ilike(f"%{folder_name}%")
                        ).first()

                        record = InstalledMod(
                            catalog_mod_id=matched_cat.id if matched_cat else None,
                            source="manual" if not matched_cat else matched_cat.source,
                            remote_id=matched_cat.remote_id if matched_cat else "",
                            title=matched_cat.title if matched_cat else folder_name.replace("_", " "),
                            folder_name=folder_name,
                            installed_date=datetime.fromtimestamp(item.stat().st_mtime),
                            is_enabled=is_enabled,
                        )
                        record.set_installed_files_list(files)
                        session.add(record)
                        found_mods.append({"title": record.title, "folder": folder_name, "status": "added"})
                    else:
                        existing.set_installed_files_list(files)
                        existing.is_enabled = is_enabled
                        found_mods.append({"title": existing.title, "folder": folder_name, "status": "updated"})

            session.commit()

        return found_mods
