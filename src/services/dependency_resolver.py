import re
from typing import List, Dict, Any, Tuple, Optional
from src.api.schemas.catalog import DependencyItem
from src.database.models import CatalogMod
from src.utils.mod_matcher import ModMatcher


# Table de correspondance pour les cas spécifiques de dépendances.
# Actuellement, seul WickedWhims est un cas spécifique avec URL en dur et liste d'alias.
SPECIAL_DEPENDENCY_CASES: List[Dict[str, Any]] = [
    {
        "title": "WickedWhims",
        "remote_id": "3169",
        "url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
        "source": "loverslab",
        "aliases": [
            "WW",
            "ww",
            "WickedWhims",
            "wickedwhims",
            "Wicked-Whims",
            "wicked-whims",
            "Wicked_Whims",
            "wicked_whims",
            "Wicked Whims",
            "wicked whims",
            "WickedWhim",
            "wickedwhim",
            "Wicked-Whim",
            "wicked-whim",
            "Wicked_Whim",
            "wicked_whim",
            "Wicked Whim",
            "wicked whim",
        ],
    },
]

SPECIAL_DEPENDENCY_REMOTE_IDS = {
    case["remote_id"] for case in SPECIAL_DEPENDENCY_CASES if "remote_id" in case
}


def find_special_dependency_case(name: str) -> Optional[Dict[str, Any]]:
    """
    Recherche si un nom de mod correspond à l'un des cas spécifiques définis
    dans la table de correspondance (insensible à la casse, tolérant aux tirets '-',
    underscores '_', espaces et versions).
    """
    if not name:
        return None

    cleaned_name = name.strip()
    # Supprime les délimiteurs entourant le nom si présent (ex: [WW] ou (WW))
    stripped_name = re.sub(r"^[\(\[\{]+|[\)\]\}]+$", "", cleaned_name).strip()
    raw_lower = stripped_name.lower()
    compressed = re.sub(r"[\s\-_.]+", "", raw_lower)

    for case in SPECIAL_DEPENDENCY_CASES:
        for alias in case.get("aliases", []):
            alias_lower = alias.strip().lower()
            alias_compressed = re.sub(r"[\s\-_.]+", "", alias_lower)

            # Correspondance directe ou après compression des séparateurs (- / _ / espace)
            if raw_lower == alias_lower or compressed == alias_compressed:
                return case

            # Tolérance pour variations suffixées de version (ex: "WickedWhims v175")
            if len(alias_compressed) > 2 and alias_compressed in compressed:
                return case

    return None


def resolve_mod_dependencies(
    raw_deps: List[Dict[str, Any]],
    session,
    installed_by_remote: Dict[Tuple[str, str], Any],
    installed_by_title: Dict[str, Any],
    is_syncing: Optional[bool] = None,
) -> List[DependencyItem]:
    """
    Resolves dependency items against database catalog and installed mods,
    returning DependencyItem objects with one of the 4 exact statuses:
    - INSTALLED
    - DETECTED_NOT_INSTALLED
    - NOT_DETECTED_SCANNING (if sync is currently running)
    - NOT_DETECTED_FINISHED (if sync is finished)
    """
    if is_syncing is None:
        from src.services.catalog_sync_service import SyncTracker
        is_syncing = SyncTracker.is_running

    items = []

    for dep in raw_deps:
        source = dep.get("source", "loverslab")
        r_id = str(dep.get("remote_id") or "")
        title = dep.get("title", "")
        url = dep.get("url", "")

        # 1. If remote_id is missing, search catalog by title or alias
        if not r_id and title:
            special_case = find_special_dependency_case(title)
            if special_case:
                r_id = special_case["remote_id"]
                url = special_case["url"]
                title = special_case["title"]
                source = special_case.get("source", source)
            else:
                # Use ModMatcher for robust regex cleaning and score-based matching
                match_res = ModMatcher.find_best_catalog_match(title, session, min_threshold=0.70)
                if match_res:
                    cat_match, match_score = match_res
                    r_id = cat_match.remote_id
                    url = cat_match.page_url
                    title = cat_match.title
                    source = cat_match.source
                else:
                    cat_match = (
                        session.query(CatalogMod)
                        .filter((CatalogMod.title.ilike(f"%{title}%")) | (CatalogMod.remote_id == title))
                        .first()
                    )
                    if cat_match:
                        r_id = cat_match.remote_id
                        url = cat_match.page_url
                        title = cat_match.title
                        source = cat_match.source

        # 2. Check installed status
        is_installed = False
        if r_id and (source, r_id) in installed_by_remote:
            is_installed = True
        elif title.lower() in installed_by_title:
            is_installed = True
        else:
            # Score check against all installed mods
            installed_list = list(installed_by_remote.values()) + list(installed_by_title.values())
            im_match = ModMatcher.find_best_installed_match(title, installed_list, min_threshold=0.85)
            if im_match:
                is_installed = True

        # 3. Determine status among the 4 states
        if is_installed:
            status = "INSTALLED"
        elif r_id:
            exists_in_catalog = (
                session.query(CatalogMod.id).filter_by(source=source, remote_id=r_id).first() is not None
            )
            if exists_in_catalog or r_id in SPECIAL_DEPENDENCY_REMOTE_IDS:
                status = "DETECTED_NOT_INSTALLED"
            elif is_syncing:
                status = "NOT_DETECTED_SCANNING"
            else:
                status = "NOT_DETECTED_FINISHED"
        else:
            if is_syncing:
                status = "NOT_DETECTED_SCANNING"
            else:
                status = "NOT_DETECTED_FINISHED"

        items.append(
            DependencyItem(
                source=source,
                remote_id=r_id,
                title=title,
                url=url,
                is_installed=is_installed,
                status=status,
            )
        )
    return items


def find_dependent_installed_mods(installed_mod_id: int, session) -> List[Dict[str, Any]]:
    """
    Identifie tous les mods installés qui dépendent du mod cible (installed_mod_id).
    Permet d'avertir l'utilisateur avant suppression si d'autres mods en ont besoin.
    """
    from src.database.models import InstalledMod
    from sqlalchemy import or_, and_

    target = session.query(InstalledMod).filter_by(id=installed_mod_id).first()
    if not target:
        return []

    target_remote_id = str(target.remote_id or "")
    target_source = target.source or "loverslab"
    target_title_lower = target.title.strip().lower()

    # Détection des cas spécifiques / alias pour le mod cible
    target_special = find_special_dependency_case(target.title)
    if not target_special and target_remote_id in SPECIAL_DEPENDENCY_REMOTE_IDS:
        for sc in SPECIAL_DEPENDENCY_CASES:
            if sc.get("remote_id") == target_remote_id:
                target_special = sc
                break

    other_installed = session.query(InstalledMod).filter(InstalledMod.id != installed_mod_id).all()
    if not other_installed:
        return []

    # Préchargement des CatalogMod associés
    cat_ids = [m.catalog_mod_id for m in other_installed if m.catalog_mod_id]
    cat_by_id = {}
    if cat_ids:
        for c in session.query(CatalogMod).filter(CatalogMod.id.in_(cat_ids)).all():
            cat_by_id[c.id] = c

    keys = [(m.source, m.remote_id) for m in other_installed if m.remote_id]
    cat_by_key = {}
    if keys:
        conditions = [and_(CatalogMod.source == s, CatalogMod.remote_id == r) for s, r in keys]
        for c in session.query(CatalogMod).filter(or_(*conditions)).all():
            cat_by_key[(c.source, c.remote_id)] = c

    dependent_mods = []

    for other in other_installed:
        cat = None
        if other.source and other.remote_id:
            cat = cat_by_key.get((other.source, other.remote_id))
        if not cat and other.catalog_mod_id:
            cat = cat_by_id.get(other.catalog_mod_id)

        if not cat:
            continue

        req_mods = cat.get_requirements_mods_list()
        depends_on_target = False

        for req in req_mods:
            r_id = str(req.get("remote_id") or "")
            r_source = req.get("source", "loverslab")
            r_title = (req.get("title") or "").strip()

            # 1. Correspondance par remote_id et source
            if target_remote_id and r_id and r_id == target_remote_id and r_source == target_source:
                depends_on_target = True
                break

            # 2. Correspondance via cas spécifique (ex: WickedWhims)
            if target_special:
                req_special = find_special_dependency_case(r_title)
                if req_special and req_special.get("remote_id") == target_special.get("remote_id"):
                    depends_on_target = True
                    break
                if r_id and r_id == target_special.get("remote_id"):
                    depends_on_target = True
                    break

            # 3. Correspondance par titre textuel ou score de similarité
            if r_title and r_title.lower() == target_title_lower:
                depends_on_target = True
                break
            if r_title and ModMatcher.match_score(r_title, target.title) >= 0.85:
                depends_on_target = True
                break

        # 4. Vérification dans le texte brut des prérequis si cas spécifique
        if not depends_on_target and cat.requirements_text and target_special:
            for alias in target_special.get("aliases", []):
                if alias.lower() in cat.requirements_text.lower():
                    depends_on_target = True
                    break

        if depends_on_target:
            dependent_mods.append({
                "id": other.id,
                "title": other.title,
                "folder_name": other.folder_name,
            })

    return dependent_mods

