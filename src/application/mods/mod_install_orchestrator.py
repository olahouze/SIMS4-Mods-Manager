"""
Orchestrator for downloading and installing catalog mods and their dependency graph.
"""

from pathlib import Path
import tempfile
from typing import Optional, Callable

from src.api.schemas.catalog import CatalogInstallRequest, CatalogInstallResponse, DependencyItem
from src.database.models import CatalogMod, InstalledMod
from src.database.manager import DatabaseManager
from src.providers import ProviderRegistry
from src.services.dependency_resolver import resolve_mod_dependencies
from src.utils.logger import logger


def perform_mod_install(
    payload: CatalogInstallRequest,
    progress_callback: Optional[Callable[[int, str, str], None]] = None,
) -> CatalogInstallResponse:
    """Orchestrates downloading and installing a mod and its required dependencies."""
    from src.services.mod_installer_service import ModInstaller

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

        not_detected_deps = [d for d in missing_dependencies if d.status == "NOT_DETECTED_FINISHED" or not d.remote_id]
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
                logger.error(
                    f"[INSTALL-DEP] ❌ URL introuvable pour '{dep_title}' (#{dep_remote_id}). Installation sautée."
                )
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
                logger.info(
                    f"[INSTALL-DEP] ✅ [{idx}/{total_missing}] Dépendance '{dep_title}' (#{dep_remote_id}) installée avec succès."
                )
                installed_dependencies.append(dep_title)
            else:
                err_msg = f"Échec de l'installation de la dépendance requise '{dep_title}': {dep_res.message}"
                logger.error(f"[INSTALL-DEP] ❌ [{idx}/{total_missing}] {err_msg}")
                if payload.allow_partial:
                    logger.warning(
                        f"[INSTALL-DEP] ⚠️ allow_partial=True : Poursuite de l'installation du mod principal '{mod_title}' malgré l'échec de la dépendance '{dep_title}'."
                    )
                    not_detected_deps.append(
                        DependencyItem(
                            source=dep_source,
                            remote_id=dep_remote_id,
                            title=dep_title,
                            url=dep_url or "",
                            status="NOT_DETECTED_FINISHED",
                        )
                    )
                else:
                    return CatalogInstallResponse(
                        success=False,
                        message=f"Installation interrompue : {err_msg}",
                        installed_dependencies=installed_dependencies,
                    )

    logger.info(
        f"[INSTALL-MAIN] Démarrage de l'installation du mod principal : '{mod_title}' ({source} #{remote_id})..."
    )

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
            magic = f.read(7)
        if magic.startswith(b"DBPF") and file_to_install.suffix.lower() != ".package":
            pkg_path = file_to_install.with_suffix(".package")
            file_to_install.replace(pkg_path)
            file_to_install = pkg_path
        elif magic.startswith(b"Rar!") and file_to_install.suffix.lower() != ".rar":
            rar_path = file_to_install.with_suffix(".rar")
            file_to_install.replace(rar_path)
            file_to_install = rar_path
        elif magic.startswith(b"7z\xbc\xaf'\x1c") and file_to_install.suffix.lower() != ".7z":
            sz_path = file_to_install.with_suffix(".7z")
            file_to_install.replace(sz_path)
            file_to_install = sz_path
        elif magic.startswith(b"PK") and file_to_install.suffix.lower() != ".zip":
            zip_path = file_to_install.with_suffix(".zip")
            file_to_install.replace(zip_path)
            file_to_install = zip_path
    except Exception as e:
        logger.debug(f"Vérification de format binaire échouée pour {file_to_install}: {e}")

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
