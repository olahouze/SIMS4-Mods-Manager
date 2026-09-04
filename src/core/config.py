import json
from pathlib import Path
from dataclasses import dataclass, asdict, fields
from typing import Optional

APP_DIR_NAME = ".sims4_mod_manager"


@dataclass
class AppConfig:
    custom_mods_dir: Optional[str] = None
    custom_game_exe: Optional[str] = None
    cached_mods_dir: Optional[str] = None
    cached_game_exe: Optional[str] = None
    auto_backup: bool = True
    adult_content_enabled: bool = True
    check_updates_on_startup: bool = True
    theme: str = "dark"
    max_workers: int = 4

    @classmethod
    def get_app_dir(cls) -> Path:
        path = Path.home() / APP_DIR_NAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_db_path(cls) -> Path:
        return cls.get_app_dir() / "sims4_mods.db"

    @classmethod
    def get_browser_profile_dir(cls) -> Path:
        path = cls.get_app_dir() / "browser_profile"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_backups_dir(cls) -> Path:
        path = cls.get_app_dir() / "backups"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_thumbnails_cache_dir(cls) -> Path:
        path = cls.get_app_dir() / "cache" / "thumbnails"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_config_file_path(cls) -> Path:
        return cls.get_app_dir() / "config.json"

    @classmethod
    def load(cls) -> "AppConfig":
        config_path = cls.get_config_file_path()
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    valid_keys = {f.name for f in fields(cls)}
                    filtered = {k: v for k, v in data.items() if k in valid_keys}
                    return cls(**filtered)
            except Exception:
                return cls()
        return cls()

    def save(self) -> None:
        config_path = self.get_config_file_path()
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=4)
