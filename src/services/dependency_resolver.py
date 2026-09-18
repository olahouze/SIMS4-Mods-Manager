from typing import List, Dict, Any, Tuple, Optional
from src.api.schemas.catalog import DependencyItem
from src.database.models import CatalogMod
from src.utils.mod_matcher import ModMatcher
from src.utils.game_dlc_matcher import GameDlcMatcher
from src.services.dependency_normalizer import clean_dependency_title, detect_game_dlc_or_base_game
from src.services.dependency_special_cases import (
    SPECIAL_DEPENDENCY_CASES,
    SPECIAL_DEPENDENCY_REMOTE_IDS,
    find_special_dependency_case,
)

__all__ = [
    "SPECIAL_DEPENDENCY_CASES",
    "SPECIAL_DEPENDENCY_REMOTE_IDS",
    "find_special_dependency_case",
    "resolve_mod_dependencies",
    "clean_dependency_title",
    "detect_game_dlc_or_base_game",
]


def resolve_mod_dependencies(
    raw_deps: List[Dict[str, Any]],
    session,
    installed_by_remote: Dict[Tuple[str, str], Any],
    installed_by_title: Dict[str, Any],
    is_syncing: Optional[bool] = None,
    catalog_remote_ids: Optional[set] = None,
    requirements_overrides: Optional[Dict[str, str]] = None,
    deduplicate: bool = True,
) -> List[DependencyItem]:
    """
    Resolves dependency items against database catalog, installed mods, and official game DLCs.
    Returns DependencyItem objects with one of the statuses:
    - INSTALLED
    - DETECTED_NOT_INSTALLED
    - NOT_DETECTED_SCANNING (if sync is currently running)
    - NOT_DETECTED_FINISHED (if sync is finished)
    - GAME_DLC (official The Sims 4 expansion / pack)
    - COMMENT_NOISE (classified as comment / not a mod by user override)
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

        clean_t = clean_dependency_title(title or "")

        # Check user override (Mod vs Comment)
        is_comment = False
        if requirements_overrides:
            t_fp = ModMatcher.canonical_fingerprint(title)
            c_fp = ModMatcher.canonical_fingerprint(clean_t)
            for ov_key, ov_val in requirements_overrides.items():
                ov_fp = ModMatcher.canonical_fingerprint(ov_key)
                if (title == ov_key or clean_t == ov_key or (ov_fp and (ov_fp == t_fp or ov_fp == c_fp))) and ov_val == "COMMENT":
                    is_comment = True
                    break

        if is_comment:
            items.append(
                DependencyItem(
                    source=source,
                    remote_id=r_id,
                    title=title,
                    url=url,
                    is_installed=False,
                    status="COMMENT_NOISE",
                    is_game_dlc=False,
                    dlc_name=None,
                    dlc_code=None,
                    is_comment=True,
                )
            )
            continue

        # 0. Check if this is an official Game DLC / Pack (multilingual support)
        is_dlc = dep.get("is_game_dlc", False) or dep.get("status") == "GAME_DLC"
        dlc_name = dep.get("dlc_name")
        dlc_code = dep.get("dlc_code")

        is_base, is_detected_dlc, det_dlc_name, det_dlc_code = detect_game_dlc_or_base_game(clean_t)
        if is_base:
            items.append(
                DependencyItem(
                    source="game_dlc",
                    remote_id="BASE_GAME",
                    title="The Sims 4 (Jeu de base)",
                    url="",
                    is_installed=True,
                    status="GAME_DLC",
                    is_game_dlc=True,
                    dlc_name="Jeu de base",
                    dlc_code="BASE_GAME",
                    is_comment=False,
                )
            )
            continue

        if not is_dlc and clean_t and is_detected_dlc:
            is_dlc = True
            dlc_name = det_dlc_name or dlc_name or title
            dlc_code = det_dlc_code or dlc_code

        if is_dlc:
            in_game = GameDlcMatcher.is_dlc_installed_in_game(dlc_code)
            is_installed = bool(in_game) if in_game is not None else False
            items.append(
                DependencyItem(
                    source="game_dlc",
                    remote_id=dlc_code or "",
                    title=f"The Sims 4 : {dlc_name}" if not title.lower().startswith("the sims 4") else title,
                    url="",
                    is_installed=is_installed,
                    status="GAME_DLC",
                    is_game_dlc=True,
                    dlc_name=dlc_name or title,
                    dlc_code=dlc_code,
                    is_comment=False,
                )
            )
            continue

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
                        .filter((CatalogMod.title.ilike(title)) | (CatalogMod.remote_id == title))
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
            # Canonical fingerprint check against installed mods
            installed_list = list(installed_by_remote.values()) + list(installed_by_title.values())
            t_fp = ModMatcher.canonical_fingerprint(title)
            for im in installed_list:
                if im.title and ModMatcher.canonical_fingerprint(im.title) == t_fp:
                    is_installed = True
                    break
            if not is_installed:
                im_match = ModMatcher.find_best_installed_match(title, installed_list, min_threshold=0.85)
                if im_match:
                    is_installed = True

        # 3. Determine status among the states
        if is_installed:
            status = "INSTALLED"
        elif r_id:
            if catalog_remote_ids is not None:
                exists_in_catalog = (source, r_id) in catalog_remote_ids
            else:
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
                is_game_dlc=False,
                dlc_name=None,
                dlc_code=None,
            )
        )

    if not deduplicate:
        return items

    # Deduplicate and merge resolved dependency items
    deduped: List[DependencyItem] = []
    seen_ids: Dict[Tuple[str, str], int] = {}
    seen_fps: Dict[str, int] = {}

    for item in items:
        s = item.source
        r = item.remote_id
        clean_t = ModMatcher.clean_mod_title(item.title) if item.title else ""
        fp = ModMatcher.canonical_fingerprint(clean_t) if clean_t else ""

        existing_idx = None
        if item.is_game_dlc:
            dlc_k = f"dlc:{item.dlc_code or item.dlc_name or item.title}".lower()
            if dlc_k in seen_fps:
                existing_idx = seen_fps[dlc_k]
            else:
                seen_fps[dlc_k] = len(deduped)
        else:
            if r and (s, r) in seen_ids:
                existing_idx = seen_ids[(s, r)]
            elif fp and fp in seen_fps:
                existing_idx = seen_fps[fp]

        if existing_idx is not None:
            existing = deduped[existing_idx]
            if item.is_installed and not existing.is_installed:
                existing.is_installed = True
                existing.status = "INSTALLED"
            if not existing.remote_id and item.remote_id:
                existing.remote_id = item.remote_id
            if not existing.url and item.url:
                existing.url = item.url
            if r:
                seen_ids[(s, r)] = existing_idx
            if fp:
                seen_fps[fp] = existing_idx
        else:
            idx = len(deduped)
            if not item.is_game_dlc:
                if r:
                    seen_ids[(s, r)] = idx
                if fp:
                    seen_fps[fp] = idx
            deduped.append(item)

    return deduped



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

