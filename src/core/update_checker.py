"""Shared utilities for mod update detection and CatalogMod resolution."""

from typing import Optional

from src.core.database import InstalledMod, CatalogMod


def check_has_update(installed_mod: InstalledMod, catalog_mod: Optional[CatalogMod]) -> bool:
    """
    Determines if an installed mod has a newer version available in the catalog.
    Centralizes the update detection logic used across multiple routes.
    """
    if not catalog_mod:
        return False

    # Primary check: compare update timestamps
    if catalog_mod.updated_date and installed_mod.version_date:
        if catalog_mod.updated_date > installed_mod.version_date:
            return True

    # Secondary check: compare version strings when both exist
    if catalog_mod.version_str and installed_mod.version_str:
        if catalog_mod.version_str.strip() != installed_mod.version_str.strip():
            return True

    # Tertiary check: catalog has a date but installed mod has none (never tracked)
    if not installed_mod.version_date and catalog_mod.updated_date:
        return True

    return False


def resolve_catalog_mod(session, installed_mod: InstalledMod) -> Optional[CatalogMod]:
    """
    Resolves the CatalogMod associated with an InstalledMod using a multi-step lookup:
    1. By (source, remote_id) pair
    2. By catalog_mod_id foreign key
    Updates the FK link if found by step 1 but not yet linked.
    """
    cat_mod = None

    # Step 1: lookup by source + remote_id
    if installed_mod.remote_id and installed_mod.source:
        cat_mod = (
            session.query(CatalogMod)
            .filter_by(source=installed_mod.source, remote_id=installed_mod.remote_id)
            .first()
        )
        if cat_mod and installed_mod.catalog_mod_id != cat_mod.id:
            installed_mod.catalog_mod_id = cat_mod.id
            session.commit()

    # Step 2: fallback to FK only if verified to match or if installed_mod has no remote_id
    if not cat_mod and installed_mod.catalog_mod_id:
        candidate = session.query(CatalogMod).filter_by(id=installed_mod.catalog_mod_id).first()
        if candidate:
            if installed_mod.remote_id and (
                candidate.remote_id != installed_mod.remote_id or candidate.source != installed_mod.source
            ):
                # Detected foreign key mismatch! Invalidate immediately to prevent mixing up mods
                installed_mod.catalog_mod_id = None
                session.commit()
            else:
                cat_mod = candidate

    return cat_mod
