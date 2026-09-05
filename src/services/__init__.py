from src.services.dependency_resolver import (
    SPECIAL_DEPENDENCY_CASES,
    SPECIAL_DEPENDENCY_REMOTE_IDS,
    find_special_dependency_case,
    resolve_mod_dependencies,
    find_dependent_installed_mods,
)
from src.providers.loverslab.matchers import (
    is_wickedwhims_name,
    is_nisa_name,
)
from src.services.catalog_sync_service import (
    SyncTracker,
    run_catalog_sync,
    check_catalog_dependencies,
)
from src.services.mod_installer_service import (
    ModInstaller,
    perform_mod_install,
)
from src.utils.file_utils import (
    sanitize_mod_folder_name,
    generate_unique_mod_folder_name,
    sanitize_filename,
)
from src.services.mod_update_service import (
    check_has_update,
    resolve_catalog_mod,
)
from src.services.mod_toggle_service import (
    ModToggleManager,
)
from src.services.game_service import (
    GameDetector,
    is_sims4_folder,
    normalize_folder_name,
    LOCALIZED_SIMS4_FOLDERS,
)

__all__ = [
    "SPECIAL_DEPENDENCY_CASES",
    "SPECIAL_DEPENDENCY_REMOTE_IDS",
    "find_special_dependency_case",
    "is_wickedwhims_name",
    "is_nisa_name",
    "resolve_mod_dependencies",
    "find_dependent_installed_mods",
    "SyncTracker",
    "run_catalog_sync",
    "check_catalog_dependencies",
    "ModInstaller",
    "perform_mod_install",
    "sanitize_mod_folder_name",
    "generate_unique_mod_folder_name",
    "sanitize_filename",
    "check_has_update",
    "resolve_catalog_mod",
    "ModToggleManager",
    "GameDetector",
    "is_sims4_folder",
    "normalize_folder_name",
    "LOCALIZED_SIMS4_FOLDERS",
]
