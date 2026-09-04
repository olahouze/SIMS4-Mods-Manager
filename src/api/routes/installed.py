import os
from typing import Optional
from fastapi import APIRouter, HTTPException

from src.api.models import (
    InstalledListResponse,
    InstalledModItem,
    InstalledToggleRequest,
    InstalledToggleResponse,
    InstalledUninstallResponse,
    InstalledScanResponse,
    InstalledOpenFolderRequest,
    InstalledOpenFolderResponse,
)
from src.core.database import DatabaseManager, InstalledMod, CatalogMod
from src.core.config import AppConfig
from src.core.game_detector import GameDetector
from src.core.mod_installer import ModInstaller
from src.core.mod_toggle import ModToggleManager
from src.core.update_checker import check_has_update

router = APIRouter(prefix="/installed", tags=["Installed Mods"])


@router.get("", response_model=InstalledListResponse)
def get_installed_mods(search: Optional[str] = None):
    """Lists all installed Sims 4 mods with status, file count, and update availability."""
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        query = session.query(InstalledMod)
        if search:
            s_clean = search.strip().lower()
            query = query.filter(
                (InstalledMod.title.ilike(f"%{s_clean}%")) | (InstalledMod.folder_name.ilike(f"%{s_clean}%"))
            )
        mods = query.order_by(InstalledMod.installed_date.desc()).all()

        # Pre-load all CatalogMods in a single query to avoid N+1
        all_catalog = session.query(CatalogMod).all()
        catalog_by_id = {cm.id: cm for cm in all_catalog}
        catalog_by_key = {(cm.source, cm.remote_id): cm for cm in all_catalog}

        items = []
        enabled_count = 0
        disabled_count = 0

        for m in mods:
            if m.is_enabled:
                enabled_count += 1
            else:
                disabled_count += 1

            # Canonical lookup by (source, remote_id) FIRST to prevent mismatched IDs
            cat_mod = None
            if m.remote_id and m.source:
                cat_mod = catalog_by_key.get((m.source, m.remote_id))
                if cat_mod and m.catalog_mod_id != cat_mod.id:
                    m.catalog_mod_id = cat_mod.id

            # Fallback to catalog_mod_id only if verified to match
            if not cat_mod and m.catalog_mod_id:
                candidate = catalog_by_id.get(m.catalog_mod_id)
                if candidate:
                    if not m.remote_id or (candidate.remote_id == m.remote_id and candidate.source == m.source):
                        cat_mod = candidate
                    else:
                        m.catalog_mod_id = None

            has_update = check_has_update(m, cat_mod)

            files_list = m.get_installed_files_list()
            thumb_url = cat_mod.thumbnail_url if cat_mod and cat_mod.thumbnail_url else ""
            author_name = cat_mod.author if cat_mod and cat_mod.author else ""
            p_url = cat_mod.page_url if cat_mod and cat_mod.page_url else ""

            items.append(
                InstalledModItem(
                    id=m.id,
                    catalog_mod_id=m.catalog_mod_id,
                    source=m.source,
                    remote_id=m.remote_id or "",
                    title=m.title,
                    author=author_name,
                    folder_name=m.folder_name,
                    thumbnail_url=thumb_url,
                    page_url=p_url,
                    is_enabled=m.is_enabled,
                    installed_date=m.installed_date,
                    version_date=m.version_date,
                    version_str=m.version_str or "",
                    files_count=len(files_list),
                    files_list=files_list,
                    backup_path=m.backup_path,
                    has_update=has_update,
                )
            )

        return InstalledListResponse(
            total=len(items),
            enabled_count=enabled_count,
            disabled_count=disabled_count,
            items=items,
        )


@router.post("/{mod_id}/toggle", response_model=InstalledToggleResponse)
def toggle_mod(mod_id: int, payload: InstalledToggleRequest = InstalledToggleRequest()):
    """Toggles a mod between enabled and disabled by renaming extensions (.package / .ts4script)."""
    ok, msg = ModToggleManager.toggle_mod(mod_id, target_state=payload.enabled)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        mod = session.query(InstalledMod).filter_by(id=mod_id).first()
        current_state = mod.is_enabled if mod else False

    return InstalledToggleResponse(
        success=True,
        message=msg,
        is_enabled=current_state,
    )


@router.delete("/{mod_id}", response_model=InstalledUninstallResponse)
def uninstall_mod(mod_id: int):
    """Deletes the mod directory from disk and cleans up database record."""
    ok, msg = ModInstaller.uninstall_mod(mod_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return InstalledUninstallResponse(success=True, message=msg)


@router.post("/scan", response_model=InstalledScanResponse)
def scan_mods_folder():
    """Scans the Sims 4 Mods directory for manually placed mods and indexes them."""
    found = ModInstaller.scan_existing_mods()
    return InstalledScanResponse(
        success=True,
        message=f"{len(found)} mod(s) scanné(s) ou mis à jour.",
        count=len(found),
        found=found,
    )


@router.post("/open-folder", response_model=InstalledOpenFolderResponse)
def open_folder(payload: InstalledOpenFolderRequest = InstalledOpenFolderRequest()):
    """Opens the Sims 4 Mods folder or a specific mod subfolder in Windows Explorer."""
    mods_dir = GameDetector.detect_mods_dir(AppConfig.load().custom_mods_dir)
    if not mods_dir or not mods_dir.exists():
        raise HTTPException(status_code=404, detail="Dossier Mods de Sims 4 introuvable.")

    target_path = mods_dir
    if payload.folder_name:
        target_path = mods_dir / payload.folder_name
        if not target_path.exists():
            raise HTTPException(status_code=404, detail=f"Sous-dossier '{payload.folder_name}' introuvable.")

    try:
        os.startfile(str(target_path))
        return InstalledOpenFolderResponse(success=True, message=f"Dossier ouvert: {target_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Impossible d'ouvrir le dossier: {e}")
