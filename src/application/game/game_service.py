"""
GameService: Facade providing Sims 4 user directories, Mods path,
Resource.cfg verification, and game launching.
Re-exports GameDetector and GameLauncher to maintain backwards compatibility.
"""

from typing import Optional
from pathlib import Path

from src.application.game.game_detector import (
    LOCALIZED_SIMS4_FOLDERS,
    normalize_folder_name,
    is_sims4_folder,
    GameDetector,
)
from src.application.game.game_launcher import GameLauncher


def launch_game(exe_path: Optional[Path] = None) -> bool:
    """Launches the Sims 4 game process."""
    return GameLauncher.launch_game(exe_path)


# Backward compatibility alias
GameService = GameDetector

__all__ = [
    "LOCALIZED_SIMS4_FOLDERS",
    "normalize_folder_name",
    "is_sims4_folder",
    "GameDetector",
    "GameLauncher",
    "GameService",
    "launch_game",
]
