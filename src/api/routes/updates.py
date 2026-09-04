import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException

from src.api.models import (
    UpdatesListResponse,
    UpdateModItem,
    UpdateModResponse,
    UpdateAllResponse,
    UpdateBatchRequest,
)
from src.core.database import DatabaseManager, InstalledMod, CatalogMod
from src.core.mod_installer import ModInstaller
from src.providers import ProviderRegistry
from src.utils.logger import logger

router = APIRouter(prefix="/updates", tags=["Updates"])


def _update_one_mod(installed_id: int) -> tuple[bool, str]:
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        im = session.query(InstalledMod).filter_by(id=installed_id).first()
        if not im:
            return False, f"Mod installé #{installed_id} introuvable."

        cat_mod = None
        if im.remote_id and im.source:
            cat_mod = session.query(CatalogMod).filter_by(source=im.source, remote_id=im.remote_id).first()
            if cat_mod and im.catalog_mod_id != cat_mod.id:
                im.catalog_mod_id = cat_mod.id
                session.commit()
        if not cat_mod and im.catalog_mod_id:
            cat_mod = session.query(CatalogMod).filter_by(id=im.catalog_mod_id).first()

        # Fallback: if cat_mod is still not found, try fetching online details using remote_id or source
        if not cat_mod and im.remote_id and im.source == "loverslab":
            provider = ProviderRegistry.get_provider(im.source)
            if provider:
                try:
                    fallback_url = f"https://www.loverslab.com/files/file/{im.remote_id}-mod/"
                    details = provider.get_mod_details(fallback_url)
                    cat_mod = CatalogMod(
                        source=im.source,
                        remote_id=im.remote_id,
                        title=details.get("title") or im.title,
                        author=details.get("author") or "",
                        page_url=fallback_url,
                        thumbnail_url=details.get("thumbnail_url") or "",
                        version_str=details.get("version_str", ""),
                        updated_date=details.get("updated_date"),
                    )
                    session.add(cat_mod)
                    session.commit()
                    im.catalog_mod_id = cat_mod.id
                    session.commit()
                except Exception as e:
                    logger.warning(f"Could not fetch online details for {im.title}: {e}")

        if not cat_mod:
            return False, f"Aucune information catalogue associée au mod '{im.title}'."

        source = cat_mod.source
        page_url = cat_mod.page_url
        title = cat_mod.title
        remote_id = cat_mod.remote_id
        version_date = cat_mod.updated_date

    provider = ProviderRegistry.get_provider(source)
    if not provider:
        return False, f"Fournisseur '{source}' introuvable."

    details = provider.get_mod_details(page_url)
    download_urls = details.get("download_urls", [])
    if not download_urls:
        return False, f"Aucun lien de téléchargement disponible pour '{title}'."

    dl_info = download_urls[0]
    dl_url = dl_info["url"] if isinstance(dl_info, dict) else dl_info

    temp_dir = Path(tempfile.gettempdir()) / "sims4_mod_manager_downloads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    dest_file = temp_dir / f"mod_{remote_id}.zip"

    ok, msg = provider.download_mod_file(dl_url, dest_file)
    if not ok:
        return False, f"Échec du téléchargement: {msg}"

    install_ok, install_msg = ModInstaller.install_mod_from_file(
        file_path=dest_file,
        catalog_mod=cat_mod,
        source=source,
        custom_title=title,
        version_date=version_date,
        version_str=details.get("version_str", ""),
    )

    try:
        dest_file.unlink(missing_ok=True)
    except Exception:
        pass

    return install_ok, install_msg


@router.get("", response_model=UpdatesListResponse)
def get_updates():
    """Returns all installed mods with their current and new versions, flagging those with updates."""
    db = DatabaseManager.get_instance()
    items = []
    with db.get_session() as session:
        installed = session.query(InstalledMod).order_by(InstalledMod.title).all()
        for im in installed:
            cat_mod = None
            if im.remote_id and im.source:
                cat_mod = session.query(CatalogMod).filter_by(source=im.source, remote_id=im.remote_id).first()
                if cat_mod and im.catalog_mod_id != cat_mod.id:
                    im.catalog_mod_id = cat_mod.id
                    session.commit()
            if not cat_mod and im.catalog_mod_id:
                cat_mod = session.query(CatalogMod).filter_by(id=im.catalog_mod_id).first()

            # Format current version
            if im.version_str and im.version_str.strip():
                cur_ver = im.version_str.strip()
            elif im.version_date:
                cur_ver = im.version_date.strftime("%d/%m/%Y %H:%M")
            else:
                cur_ver = "Inconnue"

            # Check new version and update flag
            has_update = False
            new_version_date_str = None
            new_ver = "✓ À jour"

            if cat_mod:
                if cat_mod.updated_date:
                    new_version_date_str = cat_mod.updated_date.strftime("%d/%m/%Y %H:%M")

                if cat_mod.updated_date and im.version_date and cat_mod.updated_date > im.version_date:
                    has_update = True
                elif cat_mod.version_str and im.version_str and cat_mod.version_str.strip() != im.version_str.strip():
                    has_update = True
                elif not im.version_date and cat_mod.updated_date:
                    has_update = True

                if has_update:
                    if cat_mod.version_str and cat_mod.version_str.strip():
                        new_ver = cat_mod.version_str.strip()
                    elif cat_mod.updated_date:
                        new_ver = cat_mod.updated_date.strftime("%d/%m/%Y %H:%M")
                    else:
                        new_ver = "Nouvelle version"
                else:
                    if cat_mod.version_str and cat_mod.version_str.strip():
                        new_ver = cat_mod.version_str.strip()
                    elif cat_mod.updated_date:
                        new_ver = cat_mod.updated_date.strftime("%d/%m/%Y %H:%M")
                    else:
                        new_ver = "✓ À jour"
            else:
                new_ver = "Non répertorié"

            cur_date_str = im.version_date.strftime("%d/%m/%Y %H:%M") if im.version_date else None

            items.append(
                UpdateModItem(
                    installed_id=im.id,
                    title=im.title,
                    source=im.source or "manual",
                    folder_name=im.folder_name,
                    current_version=cur_ver,
                    new_version=new_ver,
                    has_update=has_update,
                    current_version_date=cur_date_str,
                    new_version_date=new_version_date_str,
                    catalog_mod_id=cat_mod.id if cat_mod else None,
                    remote_id=im.remote_id,
                    page_url=cat_mod.page_url if cat_mod else None,
                )
            )

    # Sort so mods needing updates are displayed first, then alphabetically
    items.sort(key=lambda x: (not x.has_update, x.title.lower()))
    updatable_count = sum(1 for x in items if x.has_update)

    return UpdatesListResponse(count=updatable_count, total_installed=len(items), items=items)


@router.post("/batch", response_model=UpdateAllResponse)
def update_batch_mods(payload: UpdateBatchRequest):
    """Sequentially updates selected installed mods with automatic backup."""
    if not payload.installed_ids:
        return UpdateAllResponse(
            success=True,
            updated_count=0,
            total_count=0,
            message="Aucun mod sélectionné pour la mise à jour.",
            details=[],
        )

    updated_count = 0
    details = []
    for mod_id in payload.installed_ids:
        ok, msg = _update_one_mod(mod_id)
        if ok:
            updated_count += 1
        details.append({"id": mod_id, "success": ok, "message": msg})

    return UpdateAllResponse(
        success=updated_count > 0,
        updated_count=updated_count,
        total_count=len(payload.installed_ids),
        message=f"{updated_count}/{len(payload.installed_ids)} mod(s) sélectionné(s) mis à jour avec succès.",
        details=details,
    )


@router.post("/all", response_model=UpdateAllResponse)
def update_all_mods():
    """Sequentially updates all outdated installed mods with automatic backup."""
    db = DatabaseManager.get_instance()
    updatable_ids = []
    with db.get_session() as session:
        installed = session.query(InstalledMod).all()
        for im in installed:
            cat_mod = None
            if im.remote_id and im.source:
                cat_mod = session.query(CatalogMod).filter_by(source=im.source, remote_id=im.remote_id).first()
            if not cat_mod and im.catalog_mod_id:
                cat_mod = session.query(CatalogMod).filter_by(id=im.catalog_mod_id).first()

            has_update = False
            if cat_mod and cat_mod.updated_date and im.version_date:
                if cat_mod.updated_date > im.version_date:
                    has_update = True
            elif cat_mod and cat_mod.version_str and im.version_str:
                if cat_mod.version_str.strip() != im.version_str.strip():
                    has_update = True
            elif cat_mod and not im.version_date and cat_mod.updated_date:
                has_update = True

            if has_update:
                updatable_ids.append((im.id, im.title))

    if not updatable_ids:
        return UpdateAllResponse(
            success=True,
            updated_count=0,
            total_count=0,
            message="Tous vos mods sont déjà à jour !",
            details=[],
        )

    updated_count = 0
    details = []
    for mod_id, title in updatable_ids:
        ok, msg = _update_one_mod(mod_id)
        if ok:
            updated_count += 1
        details.append({"id": mod_id, "title": title, "success": ok, "message": msg})

    return UpdateAllResponse(
        success=updated_count > 0,
        updated_count=updated_count,
        total_count=len(updatable_ids),
        message=f"{updated_count}/{len(updatable_ids)} mod(s) mis à jour avec succès.",
        details=details,
    )


@router.post("/{installed_id}", response_model=UpdateModResponse)
def update_mod(installed_id: int):
    """Updates a single installed mod to the latest version found in catalog."""
    ok, msg = _update_one_mod(installed_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return UpdateModResponse(success=True, message=msg)

