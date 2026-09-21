import json
import os
import threading
from pathlib import Path
from dataclasses import dataclass, fields
from typing import Optional, ClassVar

APP_DIR_NAME = ".sims4_mod_manager"


@dataclass
class AppConfig:
    """Classe AppConfig : assure la gestion et l'orchestration de Appconfig."""

    custom_mods_dir: Optional[str] = None
    custom_game_exe: Optional[str] = None
    cached_mods_dir: Optional[str] = None
    cached_game_exe: Optional[str] = None
    auto_backup: bool = True
    adult_content_enabled: bool = True
    check_updates_on_startup: bool = True
    theme: str = "dark"
    language: str = "fr"
    max_workers: int = 4

    # Singleton cache with mtime-based invalidation
    _instance: ClassVar[Optional["AppConfig"]] = None
    _instance_mtime: ClassVar[float] = 0.0
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def get_app_dir(cls) -> Path:
        """Exécute l'opération get app dir.

        Returns:
            Résultat de l'opération get_app_dir.
        """
        path = Path.home() / APP_DIR_NAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_db_path(cls) -> Path:
        """Exécute l'opération get db path.

        Returns:
            Résultat de l'opération get_db_path.
        """
        env_path = os.environ.get("SIMS4_DB_PATH")
        if env_path:
            p = Path(env_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            return p
        return cls.get_app_dir() / "sims4_mods.db"

    @classmethod
    def get_browser_profile_dir(cls) -> Path:
        """Exécute l'opération get browser profile dir.

        Returns:
            Résultat de l'opération get_browser_profile_dir.
        """
        path = cls.get_app_dir() / "browser_profile"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_backups_dir(cls) -> Path:
        """Exécute l'opération get backups dir.

        Returns:
            Résultat de l'opération get_backups_dir.
        """
        path = cls.get_app_dir() / "backups"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_cache_dir(cls) -> Path:
        """Exécute l'opération get cache dir.

        Returns:
            Résultat de l'opération get_cache_dir.
        """
        path = cls.get_app_dir() / "cache"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_thumbnails_cache_dir(cls) -> Path:
        """Exécute l'opération get thumbnails cache dir.

        Returns:
            Résultat de l'opération get_thumbnails_cache_dir.
        """
        path = cls.get_cache_dir() / "thumbnails"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_images_cache_dir(cls) -> Path:
        """Exécute l'opération get images cache dir.

        Returns:
            Résultat de l'opération get_images_cache_dir.
        """
        path = cls.get_cache_dir() / "images"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_screenshots_cache_dir(cls) -> Path:
        """Exécute l'opération get screenshots cache dir.

        Returns:
            Résultat de l'opération get_screenshots_cache_dir.
        """
        path = cls.get_cache_dir() / "screenshots"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_desc_images_cache_dir(cls) -> Path:
        """Exécute l'opération get desc images cache dir.

        Returns:
            Résultat de l'opération get_desc_images_cache_dir.
        """
        path = cls.get_cache_dir() / "desc_images"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_logs_dir(cls) -> Path:
        """Exécute l'opération get logs dir.

        Returns:
            Résultat de l'opération get_logs_dir.
        """
        path = cls.get_app_dir() / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_config_file_path(cls) -> Path:
        """Exécute l'opération get config file path.

        Returns:
            Résultat de l'opération get_config_file_path.
        """
        return cls.get_app_dir() / "config.json"

    @classmethod
    def load(cls) -> "AppConfig":
        """Loads config from disk with mtime-based caching.

        Re-reads the JSON file only when the file has changed since the last load.
        Thread-safe via a class-level lock.
        """
        config_path = cls.get_config_file_path()

        with cls._instance_lock:
            try:
                current_mtime = os.path.getmtime(config_path) if config_path.exists() else 0.0
            except OSError:
                current_mtime = 0.0

            if cls._instance is not None and current_mtime == cls._instance_mtime:
                return cls._instance

            if config_path.exists():
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        valid_keys = {fi.name for fi in fields(cls) if not fi.name.startswith("_")}
                        filtered = {k: v for k, v in data.items() if k in valid_keys}
                        instance = cls(**filtered)
                except Exception:
                    instance = cls()
            else:
                instance = cls()

            cls._instance = instance
            cls._instance_mtime = current_mtime
            return instance

    def save(self) -> None:
        """Exécute l'opération save.

        Returns:
            Résultat de l'opération save.
        """
        config_path = self.get_config_file_path()
        data = {f.name: getattr(self, f.name) for f in fields(self)}
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        # Invalidate the singleton cache so the next load() picks up the new data
        with self.__class__._instance_lock:
            self.__class__._instance = self
            try:
                self.__class__._instance_mtime = config_path.stat().st_mtime
            except OSError:
                self.__class__._instance_mtime = 0.0
