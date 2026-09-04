import os
import re
import winreg
import subprocess
import unicodedata
import threading
import time
from pathlib import Path
from typing import Optional, List
from src.core.config import AppConfig
from src.utils.logger import logger
from src.utils.resource_cfg import ensure_resource_cfg

# Common localized folder names for Electronic Arts / The Sims 4 user directories
LOCALIZED_SIMS4_FOLDERS = [
    "Les Sims 4",  # French
    "The Sims 4",  # English, Russian, Polish, Portuguese, Japanese, etc.
    "Die Sims 4",  # German
    "Los Sims 4",  # Spanish
    "I Sims 4",  # Italian
    "De Sims 4",  # Dutch
    "The Sims™ 4",
    "Les Sims™ 4",
    "Die Sims™ 4",
    "Los Sims™ 4",
]


def normalize_folder_name(name: str) -> str:
    """Normalizes whitespace (including non-breaking spaces \xa0) and removes special symbols."""
    # Replace non-breaking spaces and special unicode spaces
    cleaned = name.replace("\xa0", " ").replace("\u202f", " ").replace("™", "").replace("®", "")
    # Normalize unicode
    cleaned = unicodedata.normalize("NFKD", cleaned)
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def is_sims4_folder(name: str) -> bool:
    """Checks if a directory name corresponds to Sims 4 regardless of locale or special spaces."""
    norm = normalize_folder_name(name)
    # Matches "les sims 4", "the sims 4", "sims 4", "die sims 4", etc.
    if re.search(r"(?:les|the|die|los|i|de)?\s*sims\s*4", norm, re.IGNORECASE):
        return True
    return False


class GameDetector:
    """Detects Sims 4 installation paths, Mods directory, and game executables."""

    @staticmethod
    def get_windows_documents_dirs() -> List[Path]:
        """Returns candidate paths for the user's Documents folder."""
        candidates: List[Path] = []

        # 1. Windows Registry User Shell Folders
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            ) as key:
                val, _ = winreg.QueryValueEx(key, "Personal")
                expanded = os.path.expandvars(val)
                p = Path(expanded)
                if p.exists() and p not in candidates:
                    candidates.append(p)
        except Exception as e:
            logger.debug(f"Registry Personal lookup failed: {e}")

        # 2. Standard user home Documents
        home_docs = Path.home() / "Documents"
        if home_docs.exists() and home_docs not in candidates:
            candidates.append(home_docs)

        # 3. OneDrive Documents
        onedrive_env = os.environ.get("OneDrive")
        if onedrive_env:
            onedrive_docs = Path(onedrive_env) / "Documents"
            if onedrive_docs.exists() and onedrive_docs not in candidates:
                candidates.append(onedrive_docs)

        onedrive_consumer = os.environ.get("OneDriveConsumer")
        if onedrive_consumer:
            onedrive_c_docs = Path(onedrive_consumer) / "Documents"
            if onedrive_c_docs.exists() and onedrive_c_docs not in candidates:
                candidates.append(onedrive_c_docs)

        # Fallback search for any OneDrive folder in user profile
        for sub in Path.home().glob("OneDrive*"):
            doc_sub = sub / "Documents"
            if doc_sub.exists() and doc_sub not in candidates:
                candidates.append(doc_sub)

        return candidates

    _cached_user_dir: Optional[Path] = None
    _cached_mods_dir: Optional[Path] = None
    _cached_game_exe: Optional[Path] = None

    @classmethod
    def clear_cache(cls) -> None:
        """Clears in-memory cached paths."""
        cls._cached_user_dir = None
        cls._cached_mods_dir = None
        cls._cached_game_exe = None

    @classmethod
    def detect_sims4_user_dir(cls, custom_path: Optional[str] = None) -> Optional[Path]:
        """
        Detects the 'The Sims 4' / 'Les Sims 4' user directory containing Mods/ and saves.
        Handles non-breaking spaces (\xa0) and locale variations.
        """
        if custom_path:
            p = Path(custom_path)
            if p.exists():
                return p

        if cls._cached_user_dir and cls._cached_user_dir.exists():
            return cls._cached_user_dir

        user_dir = cls._do_detect_sims4_user_dir()
        if user_dir:
            cls._cached_user_dir = user_dir
        return user_dir

    @classmethod
    def _do_detect_sims4_user_dir(cls) -> Optional[Path]:
        doc_dirs = cls.get_windows_documents_dirs()

        for doc_dir in doc_dirs:
            # Check inside Electronic Arts folder
            for ea_name in ["Electronic Arts", "electronic arts", "EA Games"]:
                ea_dir = doc_dir / ea_name
                if ea_dir.exists() and ea_dir.is_dir():
                    try:
                        for subfolder in ea_dir.iterdir():
                            if subfolder.is_dir() and is_sims4_folder(subfolder.name):
                                logger.info(f"Found Sims 4 user directory: {subfolder}")
                                return subfolder
                    except Exception as e:
                        logger.debug(f"Error scanning {ea_dir}: {e}")

            # Check directly in Documents folder
            try:
                for subfolder in doc_dir.iterdir():
                    if subfolder.is_dir() and is_sims4_folder(subfolder.name):
                        logger.info(f"Found Sims 4 user directory directly in Documents: {subfolder}")
                        return subfolder
            except Exception:
                pass

        logger.warning("Could not auto-detect Sims 4 user directory.")
        return None

    @classmethod
    def detect_mods_dir(cls, custom_path: Optional[str] = None) -> Optional[Path]:
        """
        Detects and returns the 'Mods' folder path.
        Checks in-memory cache first, then config.json persistent cache, then performs discovery.
        Ensures Resource.cfg is present.
        """
        if custom_path:
            p = Path(custom_path)
            if p.exists():
                if p.name.lower() == "mods":
                    ensure_resource_cfg(p)
                    return p
                mods_sub = p / "Mods"
                if mods_sub.exists():
                    ensure_resource_cfg(mods_sub)
                    return mods_sub
                ensure_resource_cfg(p)
                return p

        # 1. In-memory cache
        if cls._cached_mods_dir and cls._cached_mods_dir.exists():
            return cls._cached_mods_dir

        # If user directory was already detected/cached in memory, derive Mods directly
        if cls._cached_user_dir and cls._cached_user_dir.exists():
            mods_dir = cls._cached_user_dir / "Mods"
            mods_dir.mkdir(parents=True, exist_ok=True)
            ensure_resource_cfg(mods_dir)
            cls._cached_mods_dir = mods_dir
            return mods_dir

        # 2. Persistent config cache
        config = AppConfig.load()
        if config.cached_mods_dir:
            cached_p = Path(config.cached_mods_dir)
            if cached_p.exists() and cached_p.is_dir():
                cls._cached_mods_dir = cached_p
                return cached_p

        # 3. Discovery (first run or moved folder)
        mods_dir = cls._do_detect_mods_dir()
        if mods_dir:
            cls._cached_mods_dir = mods_dir
            config.cached_mods_dir = str(mods_dir)
            config.save()
        return mods_dir

    @classmethod
    def _do_detect_mods_dir(cls) -> Optional[Path]:
        user_dir = cls.detect_sims4_user_dir()
        if user_dir:
            mods_dir = user_dir / "Mods"
            mods_dir.mkdir(parents=True, exist_ok=True)
            ensure_resource_cfg(mods_dir)
            return mods_dir
        return None

    @classmethod
    def detect_game_executable(cls, custom_exe: Optional[str] = None) -> Optional[Path]:
        """
        Attempts to locate TS4_x64.exe or TS4_DX9_x64.exe from in-memory cache,
        config cache, or discovery (registry, Origin, EA App, Steam).
        """
        if custom_exe and Path(custom_exe).exists():
            return Path(custom_exe)

        # 1. In-memory cache
        if cls._cached_game_exe and cls._cached_game_exe.exists():
            return cls._cached_game_exe

        # 2. Persistent config cache
        config = AppConfig.load()
        if config.cached_game_exe:
            cached_exe = Path(config.cached_game_exe)
            if cached_exe.exists() and cached_exe.is_file():
                cls._cached_game_exe = cached_exe
                return cached_exe

        # 3. Discovery
        exe = cls._do_detect_game_executable()
        if exe:
            cls._cached_game_exe = exe
            config.cached_game_exe = str(exe)
            config.save()
        return exe

    @classmethod
    def _do_detect_game_executable(cls) -> Optional[Path]:
        # 1. Common candidate paths on drives
        common_paths = [
            r"D:\Origin\The Sims 4\Game\Bin\TS4_x64.exe",
            r"D:\Origin\The Sims 4\Game\Bin\TS4_DX9_x64.exe",
            r"C:\Program Files\EA Games\The Sims 4\Game\Bin\TS4_x64.exe",
            r"C:\Program Files (x86)\Origin Games\The Sims 4\Game\Bin\TS4_x64.exe",
            r"C:\Program Files (x86)\Steam\steamapps\common\The Sims 4\Game\Bin\TS4_x64.exe",
            r"D:\SteamLibrary\steamapps\common\The Sims 4\Game\Bin\TS4_x64.exe",
            r"E:\SteamLibrary\steamapps\common\The Sims 4\Game\Bin\TS4_x64.exe",
            r"D:\EA Games\The Sims 4\Game\Bin\TS4_x64.exe",
            r"C:\Origin Games\The Sims 4\Game\Bin\TS4_x64.exe",
        ]

        for p_str in common_paths:
            p = Path(p_str)
            if p.exists():
                logger.info(f"Found Sims 4 executable at common path: {p}")
                return p

        # 2. Check Registry for Install Dir
        for reg_root, reg_key in [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Maxis\The Sims 4"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Maxis\The Sims 4"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Electronic Arts\EA Games\The Sims 4"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Origin Games\1011164"),
        ]:
            try:
                with winreg.OpenKey(reg_root, reg_key) as key:
                    for val_name in ["Install Dir", "path", "InstallDir"]:
                        try:
                            val, _ = winreg.QueryValueEx(key, val_name)
                            install_dir = Path(val)
                            exe_candidates = [
                                install_dir / "Game" / "Bin" / "TS4_x64.exe",
                                install_dir / "Game" / "Bin" / "TS4_DX9_x64.exe",
                                install_dir / "Game" / "Bin" / "TS4_Launcher_x64.exe",
                                install_dir / "TS4_x64.exe",
                            ]
                            for exe in exe_candidates:
                                if exe.exists():
                                    logger.info(f"Found Sims 4 executable via registry: {exe}")
                                    return exe
                        except Exception:
                            continue
            except Exception:
                pass

        return None

    @classmethod
    def start_background_detection_refresh(cls) -> None:
        """
        Launches an asynchronous daemon thread to verify paths in the background.
        If the Sims 4 mods or game folder was moved or changed, updates AppConfig seamlessly.
        """

        def _worker():
            time.sleep(1.5)
            try:
                config = AppConfig.load()
                changed = False

                fresh_mods_dir = cls._do_detect_mods_dir()
                fresh_exe = cls._do_detect_game_executable()

                if fresh_mods_dir and str(fresh_mods_dir) != config.cached_mods_dir:
                    logger.info(
                        f"Déplacement ou nouvel emplacement du dossier Mods détecté en tâche de fond : {fresh_mods_dir}"
                    )
                    config.cached_mods_dir = str(fresh_mods_dir)
                    cls._cached_mods_dir = fresh_mods_dir
                    changed = True

                if fresh_exe and str(fresh_exe) != config.cached_game_exe:
                    logger.info(f"Déplacement de l'exécutable Sims 4 détecté en tâche de fond : {fresh_exe}")
                    config.cached_game_exe = str(fresh_exe)
                    cls._cached_game_exe = fresh_exe
                    changed = True

                if changed:
                    config.save()
            except Exception as e:
                logger.debug(f"Erreur lors de l'actualisation des chemins en tâche de fond : {e}")

        t = threading.Thread(target=_worker, daemon=True, name="GameDetectorRefreshThread")
        t.start()

    @classmethod
    def launch_game(cls, exe_path: Optional[Path] = None) -> bool:
        """Launches the Sims 4 game process."""
        if not exe_path:
            exe_path = cls.detect_game_executable()

        if exe_path and exe_path.exists():
            try:
                logger.info(f"Launching Sims 4 from: {exe_path}")
                subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
                return True
            except Exception as e:
                logger.error(f"Failed to launch game executable: {e}")
                return False

        # Fallback: try opening EA / Origin protocol uri or steam uri
        try:
            logger.info("Attempting to launch via steam uri steam://rungameid/1222670")
            os.startfile("steam://rungameid/1222670")
            return True
        except Exception:
            return False
