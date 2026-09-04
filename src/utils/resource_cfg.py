from pathlib import Path
from src.utils.logger import logger

DEFAULT_RESOURCE_CFG_CONTENT = """Priority 500
PackedFile *.package
PackedFile */*.package
PackedFile */*/*.package
PackedFile */*/*/*.package
PackedFile */*/*/*/*.package
PackedFile */*/*/*/*/*.package
"""


def ensure_resource_cfg(mods_dir: Path) -> bool:
    """
    Ensures that Resource.cfg exists in the Mods directory and contains
    the proper multi-level PackedFile directives for Sims 4 package scanning.
    """
    try:
        mods_dir.mkdir(parents=True, exist_ok=True)
        resource_file = mods_dir / "Resource.cfg"
        if not resource_file.exists():
            resource_file.write_text(DEFAULT_RESOURCE_CFG_CONTENT, encoding="utf-8")
            logger.info(f"Created standard Resource.cfg at {resource_file}")
            return True
        else:
            content = resource_file.read_text(encoding="utf-8", errors="ignore")
            # If it's a basic 1-level config, enhance it
            if "*/*/*/*.package" not in content:
                logger.info("Updating Resource.cfg to support deeper subfolders...")
                resource_file.write_text(DEFAULT_RESOURCE_CFG_CONTENT, encoding="utf-8")
            return True
    except Exception as e:
        logger.error(f"Error ensuring Resource.cfg: {e}")
        return False
