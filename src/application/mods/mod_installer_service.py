import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any, Callable

from src.core.config import AppConfig
from src.database.models import CatalogMod, InstalledMod
from src.database.manager import DatabaseManager
from src.application.game.game_service import GameDetector
from src.utils.archive import extract_archive, is_archive, create_backup_zip
from src.utils.logger import logger
from src.application.mods.mod_install_orchestrator import perform_mod_install

from src.utils.file_utils import (
    sanitize_mod_folder_name,
    generate_unique_mod_folder_name,
    sanitize_filename,
)

__all__ = [
    "ModInstaller",
    "perform_mod_install",
    "sanitize_mod_folder_name",
    "generate_unique_mod_folder_name",
    "sanitize_filename",
]


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
        version_str: Optional[str] = None,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        """Installs a mod from a downloaded file (archive or direct package/script)."""
        config = AppConfig.load()
        mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
        if not mods_dir:
            return False, "Dossier Mods de Sims 4 introuvable. Veuillez vérifier vos paramètres."

        title = custom_title or (catalog_mod.title if catalog_mod else file_path.stem)
        source_name = source or (catalog_mod.source if catalog_mod else "manual")
        remote_id = catalog_mod.remote_id if catalog_mod else ""
        catalog_id = catalog_mod.id if catalog_mod else None

        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            existing_installed = None
            if catalog_id:
                existing_installed = session.query(InstalledMod).filter_by(catalog_mod_id=catalog_id).first()
            if not existing_installed and remote_id and source_name:
                existing_installed = (
                    session.query(InstalledMod).filter_by(remote_id=remote_id, source=source_name).first()
                )
            if not existing_installed:
                existing_installed = session.query(InstalledMod).filter_by(title=title, source=source_name).first()

            if existing_installed and existing_installed.folder_name:
                safe_folder_name = existing_installed.folder_name
            else:
                safe_folder_name = generate_unique_mod_folder_name(
                    source_name or "manual", title or file_path.stem, mods_dir
                )

            target_mod_dir = mods_dir / (safe_folder_name or "unknown_mod")

            backup_file_path = None
            if existing_installed and target_mod_dir.exists():
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

                shutil.rmtree(target_mod_dir, ignore_errors=True)

            target_mod_dir.mkdir(parents=True, exist_ok=True)
            installed_files: List[str] = []

            file_size_mb = file_path.stat().st_size / (1024 * 1024) if file_path.exists() else 0
            if progress_callback:
                progress_callback(78, "Préparation de l'installation...", f"Fichier source : {file_size_mb:.2f} Mo")

            if is_archive(file_path):
                logger.info(
                    f"Début de la décompression de l'archive '{file_path.name}' ({file_size_mb:.2f} Mo) vers '{safe_folder_name}'..."
                )
                if progress_callback:
                    progress_callback(82, "Décompression de l'archive en cours...", f"Dossier : {safe_folder_name}")
                try:
                    extracted = extract_archive(file_path, target_mod_dir)
                    logger.info(f"Décompression réussie : {len(extracted)} fichier(s) extrait(s) pour '{title}'.")
                    for f in extracted:
                        if f.is_file():
                            logger.info(f"  • Extrait : {f.name} ({f.stat().st_size / 1024:.1f} Ko)")
                            installed_files.append(str(f.relative_to(mods_dir)))
                    if progress_callback:
                        progress_callback(92, "Décompression terminée", f"{len(installed_files)} fichier(s) extraits")
                except Exception as e:
                    logger.error(f"Erreur lors de l'extraction de l'archive {file_path.name}: {e}")
                    return False, f"Erreur lors de l'extraction de l'archive: {e}"
            else:
                if progress_callback:
                    progress_callback(85, "Copie du fichier package...", f"Dossier : {safe_folder_name}")
                target_filename = file_path.name
                try:
                    with open(file_path, "rb") as fh:
                        magic = fh.read(4)
                    if magic == b"DBPF":
                        clean_name = re.sub(r"[^a-zA-Z0-9_\-\. ]+", "_", custom_title or file_path.stem).strip()
                        if not clean_name.lower().endswith(".package"):
                            clean_name = f"{clean_name}.package"
                        target_filename = clean_name
                    elif target_filename.endswith(".zip") or target_filename.startswith("mod_"):
                        clean_name = re.sub(r"[^a-zA-Z0-9_\-\. ]+", "_", custom_title or file_path.stem).strip()
                        target_filename = f"{clean_name}.package"
                except Exception as e:
                    logger.debug(f"Header check error on {file_path.name}: {e}")

                dest_file = target_mod_dir / target_filename
                shutil.copy2(file_path, dest_file)
                installed_files.append(str(dest_file.relative_to(mods_dir)))

            # CRITICAL SIMS 4 FIX: Ensure all .ts4script are at max 1 level of subfolder
            cls._fix_ts4script_depth(target_mod_dir, mods_dir)

            installed_files = [str(p.relative_to(mods_dir)) for p in target_mod_dir.rglob("*") if p.is_file()]

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
                existing_installed.version_date = version_date or (
                    catalog_mod.updated_date if catalog_mod else existing_installed.version_date
                )
                existing_installed.version_str = version_str or (
                    catalog_mod.version_str if catalog_mod else existing_installed.version_str
                )
                existing_installed.catalog_mod_id = catalog_id or existing_installed.catalog_mod_id
                existing_installed.is_enabled = True
                if backup_file_path:
                    existing_installed.backup_path = backup_file_path
                existing_installed.set_installed_files_list(installed_files)

            if progress_callback:
                progress_callback(96, "Enregistrement en base de données...", f"{len(installed_files)} fichier(s)")

            session.commit()

        logger.info(f"Mod '{title}' successfully installed in {target_mod_dir}")
        if progress_callback:
            progress_callback(100, "Installation terminée avec succès !", f"Dossier : {safe_folder_name}")
        return True, f"Mod '{title}' installé avec succès !"

    @classmethod
    def _fix_ts4script_depth(cls, mod_dir: Path, mods_root: Path) -> None:
        """Moves any .ts4script files found in deep subfolders directly to mod_dir."""
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
                target_dir = mods_dir / (mod.folder_name or "")
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
    def verify_and_cleanup_installed_mods(cls) -> List[str]:
        """
        Scans all InstalledMod records in the database and verifies that their physical folder
        or files still exist in the Sims 4 Mods directory.
        """
        config = AppConfig.load()
        mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
        if not mods_dir or not mods_dir.exists():
            return []

        removed_titles = []
        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            installed = session.query(InstalledMod).all()
            for mod in installed:
                mod_folder = mods_dir / (mod.folder_name or "")
                if not mod_folder.exists() or not any(mod_folder.glob("*")):
                    logger.info(
                        f"Mod supprimé du disque détecté, nettoyage de la BDD : '{mod.title}' ({mod.folder_name})"
                    )
                    removed_titles.append(mod.title or "")
                    session.delete(mod)

            if removed_titles:
                session.commit()
                logger.info(
                    f"Nettoyage BDD terminé : {len(removed_titles)} mod(s) désinstallé(s) manuellement retiré(s)."
                )
        return removed_titles

    @classmethod
    def start_background_installed_mods_verifier(cls) -> None:
        """Starts an asynchronous daemon thread at startup to verify and clean up deleted mods."""

        def _worker():
            time.sleep(2.0)
            try:
                cls.verify_and_cleanup_installed_mods()
            except Exception as e:
                logger.debug(f"Erreur vérification mods installés en tâche de fond : {e}")

        from src.core.concurrency.thread_pool_manager import ThreadPoolManager

        ThreadPoolManager.get_instance().submit_io(_worker)

    @classmethod
    def scan_existing_mods(cls) -> List[Dict[str, Any]]:
        """Scans the Sims 4 Mods directory for manually placed mods and indexes them."""
        cls.verify_and_cleanup_installed_mods()

        config = AppConfig.load()
        mods_dir = GameDetector.detect_mods_dir(config.custom_mods_dir)
        if not mods_dir or not mods_dir.exists():
            return []

        found_mods = []
        db = DatabaseManager.get_instance()

        with db.get_session() as session:
            existing_by_folder = {m.folder_name: m for m in session.query(InstalledMod).all()}
            for item in mods_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    folder_name = item.name
                    files = [str(p.relative_to(mods_dir)) for p in item.rglob("*") if p.is_file()]
                    if not files:
                        continue

                    existing = existing_by_folder.get(folder_name)
                    is_enabled = not all(f.endswith(".disabled") for f in files)

                    if not existing:
                        stripped_name = re.sub(r"_\d{3,4}$", "", folder_name)
                        for prefix in ["loverslab_", "patreon_", "manual_"]:
                            if stripped_name.lower().startswith(prefix):
                                stripped_name = stripped_name[len(prefix) :]
                                break

                        clean_search = stripped_name.replace("_", " ").strip()
                        matched_cat = (
                            session.query(CatalogMod).filter(CatalogMod.title.ilike(f"%{clean_search}%")).first()
                        )
                        if not matched_cat and len(clean_search.split()) > 1:
                            first_word = clean_search.split()[0]
                            if len(first_word) >= 4:
                                matched_cat = (
                                    session.query(CatalogMod).filter(CatalogMod.title.ilike(f"%{first_word}%")).first()
                                )

                        record = InstalledMod(
                            catalog_mod_id=matched_cat.id if matched_cat else None,
                            source=matched_cat.source if matched_cat else "manual",
                            remote_id=matched_cat.remote_id if matched_cat else "",
                            title=matched_cat.title if matched_cat else clean_search,
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
