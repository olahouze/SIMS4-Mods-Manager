import re
import shutil
import threading
import time
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any, Callable

from src.api.schemas.catalog import CatalogInstallRequest, CatalogInstallResponse
from src.core.config import AppConfig
from src.database.models import CatalogMod, InstalledMod
from src.database.manager import DatabaseManager
from src.services.game_service import GameDetector
from src.providers import ProviderRegistry
from src.services.dependency_resolver import resolve_mod_dependencies
from src.utils.archive import extract_archive, is_archive, create_backup_zip
from src.utils.logger import logger


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

            if existing_installed:
                safe_folder_name = existing_installed.folder_name
            else:
                safe_folder_name = generate_unique_mod_folder_name(source_name, title, mods_dir)

            target_mod_dir = mods_dir / safe_folder_name

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
                    with open(file_path, "rb") as f:
                        magic = f.read(4)
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
                mod_folder = mods_dir / mod.folder_name
                if not mod_folder.exists() or not any(mod_folder.glob("*")):
                    logger.info(
                        f"Mod supprimé du disque détecté, nettoyage de la BDD : '{mod.title}' ({mod.folder_name})"
                    )
                    removed_titles.append(mod.title)
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

        t = threading.Thread(target=_worker, daemon=True, name="InstalledModsVerifierThread")
        t.start()

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
            for item in mods_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    folder_name = item.name
                    files = [str(p.relative_to(mods_dir)) for p in item.rglob("*") if p.is_file()]
                    if not files:
                        continue

                    existing = session.query(InstalledMod).filter_by(folder_name=folder_name).first()
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


def perform_mod_install(
    payload: CatalogInstallRequest,
    progress_callback: Optional[Callable[[int, str, str], None]] = None,
) -> CatalogInstallResponse:
    """Orchestre le téléchargement et l'installation d'un mod et de ses dépendances."""
    db = DatabaseManager.get_instance()
    cat_mod = None
    with db.get_session() as session:
        if payload.catalog_mod_id:
            cat_mod = session.query(CatalogMod).filter_by(id=payload.catalog_mod_id).first()
        elif payload.source and payload.remote_id:
            cat_mod = session.query(CatalogMod).filter_by(source=payload.source, remote_id=payload.remote_id).first()

    source = cat_mod.source if cat_mod else (payload.source or "loverslab")
    page_url = cat_mod.page_url if cat_mod else payload.page_url
    mod_title = cat_mod.title if cat_mod else (payload.title or "Mod")
    remote_id = cat_mod.remote_id if cat_mod else (payload.remote_id or "unknown")
    version_date = cat_mod.updated_date if cat_mod else payload.updated_date

    if not page_url:
        return CatalogInstallResponse(success=False, message="Page URL ou identifiant du mod introuvable.")

    installed_dependencies = []
    not_detected_deps = []
    if payload.install_dependencies:
        req_mods = cat_mod.get_requirements_mods_list() if cat_mod else []
        req_status = cat_mod.requirements_status if cat_mod else "NONE"

        if (not req_mods or req_status in [None, "NONE"]) and page_url:
            try:
                provider = ProviderRegistry.get_provider(source)
                if provider:
                    logger.info(f"[INSTALL-DEP] Analyse préalable des dépendances pour '{mod_title}' ({page_url})...")
                    det = provider.get_mod_details(page_url)
                    req_mods = det.get("requirements_mods", [])
                    req_status = det.get("requirements_status", "NONE")
                    if cat_mod:
                        with db.get_session() as s:
                            cm = s.query(CatalogMod).filter_by(id=cat_mod.id).first()
                            if cm:
                                cm.requirements_text = det.get("requirements_text")
                                cm.requirements_status = req_status
                                cm.set_requirements_mods_list(req_mods)
                                s.commit()
            except Exception as e:
                logger.warning(f"[INSTALL-DEP] Impossible d'analyser les prérequis pour '{mod_title}': {e}")

        with db.get_session() as session:
            all_inst = session.query(InstalledMod).all()
            installed_by_remote = {(im.source, im.remote_id): im for im in all_inst if im.remote_id}
            installed_by_title = {im.title.lower(): im for im in all_inst if im.title}

            resolved_deps = resolve_mod_dependencies(
                req_mods,
                session,
                installed_by_remote,
                installed_by_title,
            )

        already_installed = [d for d in resolved_deps if d.is_installed or d.status == "INSTALLED"]
        missing_dependencies = [d for d in resolved_deps if not d.is_installed and d.status != "INSTALLED"]

        not_detected_deps = [
            d for d in missing_dependencies if d.status == "NOT_DETECTED_FINISHED" or not d.remote_id
        ]
        if not_detected_deps:
            names = ", ".join(f"'{d.title}'" for d in not_detected_deps)
            logger.warning(
                f"[INSTALL-DEP] ⚠️ Installation partielle pour '{mod_title}' : "
                f"{len(not_detected_deps)} dépendance(s) introuvables ignorée(s) : {names}"
            )
            missing_dependencies = [d for d in missing_dependencies if d not in not_detected_deps]

        logger.info(
            f"[INSTALL-DEP] Analyse pour '{mod_title}': {len(resolved_deps)} dépendance(s) au total "
            f"({len(already_installed)} déjà installée(s), {len(missing_dependencies)} à installer, "
            f"{len(not_detected_deps)} non trouvée(s))."
        )

        for dep in already_installed:
            logger.info(f"[INSTALL-DEP] -> Dépendance déjà installée : '{dep.title}' (#{dep.remote_id})")

        total_missing = len(missing_dependencies)
        for idx, dep in enumerate(missing_dependencies, start=1):
            dep_source = dep.source or "loverslab"
            dep_remote_id = dep.remote_id or ""
            dep_title = dep.title or f"Mod #{dep_remote_id}"
            dep_url = dep.url

            if not dep_url and dep_remote_id:
                with db.get_session() as s:
                    c_dep = s.query(CatalogMod).filter_by(source=dep_source, remote_id=dep_remote_id).first()
                    if c_dep and c_dep.page_url:
                        dep_url = c_dep.page_url
                if not dep_url and dep_source == "loverslab":
                    dep_url = f"https://www.loverslab.com/files/file/{dep_remote_id}/"

            logger.info(
                f"[INSTALL-DEP] [{idx}/{total_missing}] Démarrage téléchargement & installation dépendance : "
                f"'{dep_title}' (Source: {dep_source}, ID: #{dep_remote_id}, URL: {dep_url})"
            )

            if progress_callback:
                pct = int(10 + (idx - 1) / max(total_missing, 1) * 35)
                progress_callback(
                    pct,
                    f"Installation dépendance ({idx}/{total_missing}) : {dep_title}...",
                    f"ID #{dep_remote_id}",
                )

            if not dep_url:
                logger.error(f"[INSTALL-DEP] ❌ URL introuvable pour '{dep_title}' (#{dep_remote_id}). Installation sautée.")
                continue

            dep_payload = CatalogInstallRequest(
                source=dep_source,
                remote_id=dep_remote_id,
                page_url=dep_url,
                title=dep_title,
                install_dependencies=False,  # Prevent cyclic loops
            )
            dep_res = perform_mod_install(dep_payload, progress_callback=progress_callback)
            if dep_res.success:
                logger.info(f"[INSTALL-DEP] ✅ [{idx}/{total_missing}] Dépendance '{dep_title}' (#{dep_remote_id}) installée avec succès.")
                installed_dependencies.append(dep_title)
            else:
                err_msg = f"Échec de l'installation de la dépendance requise '{dep_title}': {dep_res.message}"
                logger.error(f"[INSTALL-DEP] ❌ [{idx}/{total_missing}] {err_msg}")
                return CatalogInstallResponse(
                    success=False,
                    message=f"Installation interrompue : {err_msg}",
                    installed_dependencies=installed_dependencies,
                )

    logger.info(f"[INSTALL-MAIN] Démarrage de l'installation du mod principal : '{mod_title}' ({source} #{remote_id})...")

    provider = ProviderRegistry.get_provider(source)
    if not provider:
        return CatalogInstallResponse(success=False, message=f"Fournisseur source '{source}' non supporté.")

    if progress_callback:
        progress_callback(2, "Analyse de la page du mod...", f"Source : {source}")

    details = provider.get_mod_details(page_url)
    download_urls = details.get("download_urls", [])
    if not download_urls:
        ext_links = details.get("external_links", [])
        if ext_links:
            return CatalogInstallResponse(
                success=False, message=f"Téléchargement externe requis : {', '.join(ext_links[:2])}"
            )
        return CatalogInstallResponse(success=False, message="Aucun lien de téléchargement trouvé pour ce mod.")

    dl_info = download_urls[0]
    dl_url = dl_info["url"] if isinstance(dl_info, dict) else dl_info

    temp_dir = Path(tempfile.gettempdir()) / "sims4_mod_manager_downloads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    filename = f"mod_{remote_id}.zip"
    dest_file = temp_dir / filename

    if progress_callback:
        progress_callback(5, "Démarrage du téléchargement...", f"{filename}")

    ok, msg = provider.download_mod_file(dl_url, dest_file, progress_callback=progress_callback)
    if not ok:
        logger.error(f"Échec du téléchargement du mod '{mod_title}' ({source} #{remote_id}): {msg}")
        return CatalogInstallResponse(success=False, message=f"Échec du téléchargement: {msg}")

    file_to_install = Path(msg) if Path(msg).exists() else dest_file
    try:
        with open(file_to_install, "rb") as f:
            magic = f.read(4)
        if magic == b"DBPF" and file_to_install.suffix.lower() != ".package":
            pkg_path = file_to_install.with_suffix(".package")
            file_to_install.replace(pkg_path)
            file_to_install = pkg_path
    except Exception as e:
        logger.debug(f"Vérification DBPF échouée pour {file_to_install}: {e}")

    install_ok, install_msg = ModInstaller.install_mod_from_file(
        file_path=file_to_install,
        catalog_mod=cat_mod,
        source=source,
        custom_title=mod_title,
        version_date=version_date,
        version_str=details.get("version_str", ""),
        progress_callback=progress_callback,
    )

    if not install_ok:
        logger.error(f"Échec de l'installation du mod '{mod_title}' ({source} #{remote_id}): {install_msg}")
    else:
        logger.info(f"Installation réussie du mod '{mod_title}' ({source} #{remote_id})")
        if not_detected_deps:
            names = ", ".join(f"'{d.title}'" for d in not_detected_deps)
            install_msg = (
                f"Installation partielle réussie ! Le mod '{mod_title}' a été installé avec succès, "
                f"mais {len(not_detected_deps)} dépendance(s) introuvable(s) ({names}) n'ont pas pu être ajoutées."
            )

    try:
        file_to_install.unlink(missing_ok=True)
        dest_file.unlink(missing_ok=True)
    except Exception as e:
        logger.debug(f"Nettoyage des fichiers temporaires échoué: {e}")

    return CatalogInstallResponse(
        success=install_ok,
        message=install_msg,
        installed_dependencies=installed_dependencies,
    )
