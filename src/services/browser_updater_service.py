import sys
import re
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable, Tuple
from src.utils.logger import logger


class BrowserUpdaterService:
    """
    Service responsible for verifying Playwright Chromium browser availability
    and executing just-in-time updates/downloads with real-time progress parsing.
    """

    PROGRESS_REGEX = re.compile(r"(\d+)%\s+of\s+([\d\.]+\s*[a-zA-Z]+)", re.IGNORECASE)
    SIMPLE_PERCENT_REGEX = re.compile(r"(\d+)%")

    @classmethod
    def is_chromium_ready(cls) -> bool:
        """
        Tests if Playwright Chromium can be launched without error.
        Returns True if operational, False otherwise.
        """
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                # Test chromium executable resolution
                try:
                    exe_path = p.chromium.executable_path
                    if not exe_path or not Path(exe_path).exists():
                        return False
                except Exception:
                    return False

                # Quick launch test
                browser = p.chromium.launch(headless=True)
                browser.close()
                return True
        except Exception as e:
            logger.debug(f"Vérification Playwright Chromium : non disponible ({e})")
            return False

    @classmethod
    def install_chromium_stream(
        cls,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Tuple[bool, str]:
        """
        Executes 'python -m playwright install chromium' in a subprocess,
        streaming progress updates to the provided callback.

        Args:
            progress_callback: function(percent: int, message: str)
            cancel_event: threading.Event to signal cancellation

        Returns:
            (success: bool, error_or_success_message: str)
        """
        cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
        logger.info(f"Lancement de l'installation de Chromium: {' '.join(cmd)}")

        if progress_callback:
            progress_callback(0, "Démarrage du téléchargement...")

        try:
            # Creation flag for Windows to prevent flashing console window
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creation_flags,
                encoding="utf-8",
                errors="replace",
            )

            last_percent = 0
            last_message = "Téléchargement en cours..."

            while proc.poll() is None:
                if cancel_event and cancel_event.is_set():
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    logger.info("Installation de Chromium annulée par l'utilisateur.")
                    return False, "Téléchargement annulé par l'utilisateur."

                line = proc.stdout.readline()
                if line:
                    line_clean = line.strip()
                    logger.debug(f"[Playwright Install]: {line_clean}")

                    match_detail = cls.PROGRESS_REGEX.search(line_clean)
                    if match_detail:
                        pct = int(match_detail.group(1))
                        size_str = match_detail.group(2)
                        last_percent = pct
                        last_message = f"Téléchargement : {pct}% sur {size_str}"
                        if progress_callback:
                            progress_callback(pct, last_message)
                    else:
                        match_simple = cls.SIMPLE_PERCENT_REGEX.search(line_clean)
                        if match_simple:
                            pct = int(match_simple.group(1))
                            last_percent = pct
                            last_message = f"Téléchargement : {pct}%"
                            if progress_callback:
                                progress_callback(pct, last_message)
                        elif "Downloading" in line_clean:
                            last_message = line_clean
                            if progress_callback:
                                progress_callback(last_percent, last_message)

            # Process completed
            returncode = proc.wait()
            if returncode == 0:
                if progress_callback:
                    progress_callback(100, "Installation finalisée avec succès.")
                logger.info("Chromium pour Playwright installé avec succès.")
                return True, "Installation de Chromium réussie."
            else:
                remaining_output = proc.stdout.read() if proc.stdout else ""
                err_msg = f"Erreur lors de l'installation (code {returncode}): {remaining_output.strip()}"
                logger.error(err_msg)
                return False, err_msg

        except Exception as e:
            logger.error(f"Exception lors du téléchargement de Chromium: {e}")
            return False, str(e)
