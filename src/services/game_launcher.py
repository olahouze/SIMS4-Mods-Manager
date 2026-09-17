"""
GameLauncher: Locates Sims 4 game executable via common paths, EA app, Origin, Steam,
and Windows registry, and handles process execution.
"""
import os
import winreg
import subprocess
from pathlib import Path
from typing import Optional

from src.core.config import AppConfig
from src.utils.logger import logger


class GameLauncher:
    """Detects game executable and handles process launching."""

    _cached_game_exe: Optional[Path] = None

    @classmethod
    def clear_cache(cls) -> None:
        cls._cached_game_exe = None

    @classmethod
    def detect_game_executable(cls, custom_exe: Optional[str] = None) -> Optional[Path]:
        """Locates TS4_x64.exe or TS4_DX9_x64.exe."""
        if custom_exe and Path(custom_exe).exists():
            return Path(custom_exe)

        if cls._cached_game_exe and cls._cached_game_exe.exists():
            return cls._cached_game_exe

        config = AppConfig.load()
        if config.cached_game_exe:
            cached_exe = Path(config.cached_game_exe)
            if cached_exe.exists() and cached_exe.is_file():
                cls._cached_game_exe = cached_exe
                return cached_exe

        exe = cls._do_detect_game_executable()
        if exe:
            cls._cached_game_exe = exe
            config.cached_game_exe = str(exe)
            config.save()
        return exe

    @classmethod
    def _do_detect_game_executable(cls) -> Optional[Path]:
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

        try:
            logger.info("Attempting to launch via steam uri steam://rungameid/1222670")
            os.startfile("steam://rungameid/1222670")
            return True
        except Exception:
            return False
