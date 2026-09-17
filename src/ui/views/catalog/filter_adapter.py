"""
Filter adapter converting UI filter state into REST API query parameters for catalog endpoints.
"""
from typing import Dict, Any, Optional

__all__ = ["build_catalog_api_params"]


def build_catalog_api_params(
    filter_state: Dict[str, Any],
    current_page: int,
    page_size: int,
) -> Dict[str, Any]:
    """Translates UI filter dropdowns and search inputs into REST API query parameters."""
    source_param: Optional[str] = None
    if filter_state.get("source") == "LoversLab":
        source_param = "loverslab"
    elif filter_state.get("source") == "Patreon":
        source_param = "patreon"

    type_param = filter_state.get("mod_type")
    if type_param == "all":
        type_param = None

    access_param: Optional[str] = None
    acc_text = str(filter_state.get("access", ""))
    if acc_text in ("direct", "needs_account", "needs_sub", "unlocked", "public", "locked"):
        access_param = acc_text
    elif "Directement" in acc_text:
        access_param = "direct"
    elif "connexion" in acc_text.lower():
        access_param = "needs_account"
    elif "abonnement" in acc_text.lower() and "débloqué" not in acc_text.lower():
        access_param = "needs_sub"
    elif "Débloqué" in acc_text:
        access_param = "unlocked"
    elif "Public" in acc_text:
        access_param = "public"
    elif "Verrouillé" in acc_text:
        access_param = "locked"

    sort_val = str(filter_state.get("sort", ""))
    sort_param = "az" if ("A-Z" in sort_val or sort_val == "az") else "recent"

    status_param: Optional[str] = None
    stat_text = str(filter_state.get("status", ""))
    if stat_text in ("installed", "not_installed", "updates_available"):
        status_param = stat_text
    elif "Déjà installés" in stat_text:
        status_param = "installed"
    elif "Non installés" in stat_text:
        status_param = "not_installed"
    elif "Mises à jour" in stat_text:
        status_param = "updates_available"

    return {
        "search": filter_state.get("search") or None,
        "source": source_param,
        "access": access_param,
        "status": status_param,
        "mod_type": type_param,
        "sort": sort_param,
        "page": current_page,
        "limit": page_size,
    }
