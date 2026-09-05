from typing import List, Optional, Tuple
from src.database.models import InstalledMod
from src.database.manager import DatabaseManager
from src.core.config import AppConfig
from src.services.game_service import GameDetector
from src.utils.logger import logger


class ModToggleManager:
    """Handles enabling and disabling installed Sims 4 mods without deletion."""

    @classmethod
    def toggle_mod(cls, installed_mod_id: int, target_state: Optional[bool] = None) -> Tuple[bool, str]:
        """
        Toggles the enabled status of an installed mod.
        If target_state is None, inverts current state.
        """
        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            mod = session.query(InstalledMod).filter_by(id=installed_mod_id).first()
            if not mod:
                return False, f"Mod with ID {installed_mod_id} not found."

            new_state = (not mod.is_enabled) if target_state is None else target_state
            if mod.is_enabled == new_state:
                return True, f"Mod '{mod.title}' is already {'enabled' if new_state else 'disabled'}."

            mods_dir = GameDetector.detect_mods_dir(AppConfig.load().custom_mods_dir)
            if not mods_dir or not mods_dir.exists():
                return False, "Sims 4 Mods folder could not be found."

            mod_folder = mods_dir / mod.folder_name
            if not mod_folder.exists():
                return False, f"Mod folder '{mod.folder_name}' does not exist on disk."

            updated_files: List[str] = []
            for file_path in mod_folder.rglob("*"):
                if not file_path.is_file():
                    continue

                rel_path = file_path.relative_to(mods_dir)

                if not new_state:
                    # Disabling: rename .package -> .package.disabled, .ts4script -> .ts4script.disabled
                    if file_path.suffix.lower() in [".package", ".ts4script"]:
                        new_file_path = file_path.with_name(file_path.name + ".disabled")
                        file_path.rename(new_file_path)
                        updated_files.append(str(new_file_path.relative_to(mods_dir)))
                    else:
                        updated_files.append(str(rel_path))
                else:
                    # Enabling: rename .disabled back
                    if file_path.name.lower().endswith(".package.disabled"):
                        new_file_path = file_path.with_name(file_path.name[:-9])  # remove .disabled
                        file_path.rename(new_file_path)
                        updated_files.append(str(new_file_path.relative_to(mods_dir)))
                    elif file_path.name.lower().endswith(".ts4script.disabled"):
                        new_file_path = file_path.with_name(file_path.name[:-9])
                        file_path.rename(new_file_path)
                        updated_files.append(str(new_file_path.relative_to(mods_dir)))
                    else:
                        updated_files.append(str(rel_path))

            mod.is_enabled = new_state
            mod.set_installed_files_list(updated_files)
            session.commit()

            status_str = "activé" if new_state else "désactivé"
            logger.info(f"Mod '{mod.title}' {status_str} avec succès.")
            return True, f"Mod '{mod.title}' {status_str}."
