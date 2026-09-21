"""SQLAlchemy query builder and SQL-level filters for catalog search."""

from typing import Optional
from sqlalchemy.orm import Session, Query as OrmQuery

from src.database.models import CatalogMod, InstalledMod
from src.utils.mod_type_classifier import ModTypeClassifier


def build_catalog_query(
    session: Session,
    search: Optional[str] = None,
    source: Optional[str] = None,
    access: Optional[str] = None,
    status: Optional[str] = None,
    mod_type: Optional[str] = None,
    sort: Optional[str] = "recent",
) -> OrmQuery:
    """Builds and returns the SQLAlchemy Query with all filter and sort criteria applied."""
    query = session.query(CatalogMod)

    if search:
        s_clean = search.strip()
        query = query.filter(
            (CatalogMod.title.ilike(f"%{s_clean}%"))
            | (CatalogMod.author.ilike(f"%{s_clean}%"))
            | (CatalogMod.tags.ilike(f"%{s_clean}%"))
        )

    if source and source.lower() != "all":
        query = query.filter(CatalogMod.source == source.lower())

    if mod_type:
        type_filter = ModTypeClassifier.get_sql_filter(mod_type, CatalogMod)
        if type_filter is not None:
            query = query.filter(type_filter)

    # Support access filters passed in either access or status param
    if status and status.lower() in [
        "direct",
        "site_direct",
        "needs_account",
        "account",
        "connexion",
        "needs_sub",
        "subscription",
        "abonnement",
        "locked",
    ]:
        if not access or access.lower() == "all":
            access = status
            status = None

    if access and access.lower() != "all":
        acc = access.lower()
        if acc in ["direct", "site_direct"]:
            query = query.filter(
                CatalogMod.source != "patreon",
                (CatalogMod.patreon_status == "NONE")
                | (CatalogMod.patreon_status.is_(None))
                | (CatalogMod.patreon_status == ""),
                ~CatalogMod.tags.ilike("%Patreon%"),
            )
        elif acc in ["needs_account", "account", "connexion"]:
            query = query.filter(
                (CatalogMod.source == "patreon")
                | (CatalogMod.patreon_status == "PUBLIC")
                | (CatalogMod.tags.ilike("%Patreon%"))
            ).filter(
                CatalogMod.patreon_status != "LOCKED",
                CatalogMod.patreon_status != "UNLOCKED",
            )
        elif acc in ["needs_sub", "subscription", "abonnement", "locked", "verrouillé"]:
            query = query.filter(
                (CatalogMod.patreon_status == "LOCKED")
                | (
                    (CatalogMod.source == "patreon")
                    & (CatalogMod.patreon_tier != "")
                    & (CatalogMod.patreon_status != "UNLOCKED")
                )
            )
        elif acc in ["unlocked", "débloqué"]:
            query = query.filter(CatalogMod.patreon_status == "UNLOCKED")
        elif acc in ["public", "gratuit"]:
            query = query.filter(CatalogMod.patreon_status.in_(["PUBLIC", "NONE"]))

    # SQL-level status filtering
    if status and status.lower() not in ["all", ""]:
        st = status.lower()
        installed_match = (
            (InstalledMod.source == CatalogMod.source) & (InstalledMod.remote_id == CatalogMod.remote_id)
        ) | (
            (InstalledMod.catalog_mod_id == CatalogMod.id)
            & ((InstalledMod.remote_id.is_(None)) | (InstalledMod.remote_id == ""))
        )

        if st in ["installed", "installe", "installé"]:
            query = query.filter(session.query(InstalledMod.id).filter(installed_match).exists())
        elif st in ["not_installed", "non_installe", "non installé", "disponible"]:
            query = query.filter(~session.query(InstalledMod.id).filter(installed_match).exists())
        elif st == "updates_available":
            has_newer = (CatalogMod.updated_date.isnot(None)) & (
                InstalledMod.version_date.is_(None)
                | (CatalogMod.updated_date > InstalledMod.version_date)
                | (
                    CatalogMod.version_str.isnot(None)
                    & InstalledMod.version_str.isnot(None)
                    & (CatalogMod.version_str != InstalledMod.version_str)
                )
            )
            query = query.filter(session.query(InstalledMod.id).filter(installed_match, has_newer).exists())

    if sort in ["az", "title"]:
        query = query.order_by(CatalogMod.title.asc(), CatalogMod.id.desc())
    else:
        query = query.order_by(CatalogMod.updated_date.desc().nullslast(), CatalogMod.id.desc())

    return query
