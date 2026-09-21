"""Routes API REST pour les mods installés (Front -> Back).

Délègue l'intégralité des opérations au service applicatif InstalledModsService
sans accès direct aux sessions de base de données.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException

from src.api.schemas.installed import (
    InstalledListResponse,
    InstalledOpenFolderRequest,
    InstalledOpenFolderResponse,
    InstalledScanResponse,
    InstalledToggleRequest,
    InstalledToggleResponse,
    InstalledUninstallResponse,
    ModDependentsResponse,
)
from src.application.mods.installed_mods_service import InstalledModsService

router = APIRouter(prefix="/installed", tags=["Installed Mods"])
_installed_service = InstalledModsService()


@router.get("", response_model=InstalledListResponse)
def get_installed_mods(search: Optional[str] = None) -> InstalledListResponse:
    """Liste tous les mods installés avec statut, comptage de fichiers et mises à jour disponibles."""
    return _installed_service.list_installed_mods(search=search)


@router.post("/{mod_id}/toggle", response_model=InstalledToggleResponse)
def toggle_mod(mod_id: int, payload: InstalledToggleRequest = InstalledToggleRequest()) -> InstalledToggleResponse:
    """Active ou désactive un mod en renommant ses extensions."""
    res = _installed_service.toggle_mod(mod_id, target_state=payload.enabled)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message)
    return res


@router.get("/{mod_id}/dependents", response_model=ModDependentsResponse)
def get_mod_dependents(mod_id: int) -> ModDependentsResponse:
    """Retourne la liste des mods installés qui dépendent de ce mod."""
    res = _installed_service.get_dependents(mod_id)
    if not res.mod_title:
        raise HTTPException(status_code=404, detail="Mod introuvable dans la base de données.")
    return res


@router.delete("/{mod_id}", response_model=InstalledUninstallResponse)
def uninstall_mod(mod_id: int) -> InstalledUninstallResponse:
    """Supprime le dossier du mod du disque et nettoie la base de données."""
    res = _installed_service.uninstall_mod(mod_id)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message)
    return res


@router.post("/scan", response_model=InstalledScanResponse)
def scan_mods_folder() -> InstalledScanResponse:
    """Scanne le répertoire Mods pour indexer les ajouts manuels."""
    return _installed_service.scan_mods()


@router.post("/open-folder", response_model=InstalledOpenFolderResponse)
def open_folder(payload: InstalledOpenFolderRequest = InstalledOpenFolderRequest()) -> InstalledOpenFolderResponse:
    """Ouvre le dossier Mods ou le dossier d'un mod dans l'explorateur."""
    res = _installed_service.open_mod_folder(payload.folder_name)
    if not res.success:
        status = 404 if "introuvable" in res.message or "n'existe pas" in res.message else 500
        raise HTTPException(status_code=status, detail=res.message)
    return res
