import socket
import time
from pathlib import Path
from typing import Optional, Callable, Tuple

from src.utils.logger import logger

# Centralized list of external hosting domains used for redirect detection (§3.5)
EXTERNAL_HOSTING_DOMAINS = [
    "gofile.io",
    "mega.nz",
    "mega.co.nz",
    "mediafire.com",
    "drive.google.com",
    "dropbox.com",
    "simfileshare.net",
]


def is_external_hosted(url: str) -> Optional[str]:
    """Returns the matched external domain if the URL points to an external host, else None."""
    url_lower = url.lower()
    for domain in EXTERNAL_HOSTING_DOMAINS:
        if domain in url_lower:
            return domain
    return None


def is_port_available(host: str, port: int) -> bool:
    """Checks whether a port is currently available on the specified host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except (OSError, socket.error):
            return False


def find_available_port(host: str = "127.0.0.1", start_port: int = 8000, max_attempts: int = 100) -> int:
    """
    Finds the first free port starting from `start_port`.
    If none in range is available, lets the OS pick an ephemeral free port.
    """
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(host, port):
            if port != start_port:
                logger.info(f"Port par défaut {start_port} indisponible. Port libre alloué : {port}")
            return port

    # Fallback to OS assigned port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        allocated_port = s.getsockname()[1]
        logger.warning(
            f"Plage de ports {start_port}-{start_port + max_attempts} saturée. Port éphémère alloué : {allocated_port}"
        )
        return allocated_port


def stream_download(
    response,
    dest_path: Path,
    progress_callback: Optional[Callable[[int, str, str], None]] = None,
    phase_label: str = "Téléchargement",
) -> Tuple[bool, str]:
    """
    Streams an HTTP response body to a file with progress tracking, speed calculation, and logging.

    Shared by all providers (LoversLab, Patreon) to avoid duplicating the download loop.
    Handles both streaming (iter_content) and non-streaming (content) responses gracefully.
    """
    total_size = int(response.headers.get("Content-Length") or 0)
    downloaded = 0
    start_time = time.time()
    last_ui_time = start_time
    last_log_time = start_time

    def _calc_progress() -> Tuple[int, str]:
        elapsed = time.time() - start_time
        speed_mb = (downloaded / max(elapsed, 0.001)) / (1024 * 1024)
        speed_str = f"{speed_mb:.2f} Mo/s" if speed_mb >= 1.0 else f"{speed_mb * 1024:.0f} Ko/s"

        if total_size > 0:
            pct = min(int((downloaded / total_size) * 75), 75)
            down_mb = downloaded / (1024 * 1024)
            tot_mb = total_size / (1024 * 1024)
            detail = f"{down_mb:.1f} / {tot_mb:.1f} Mo • {speed_str}"
        else:
            down_mb = downloaded / (1024 * 1024)
            pct = min(int(down_mb * 2), 70)
            detail = f"{down_mb:.1f} Mo • {speed_str}"
        return pct, detail

    with open(dest_path, "wb") as f:
        try:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    pct, detail = _calc_progress()

                    if progress_callback and (now - last_ui_time >= 0.2):
                        progress_callback(pct, f"{phase_label} en cours...", detail)
                        last_ui_time = now

                    if now - last_log_time >= 3.0:
                        logger.info(f"[{phase_label}] {dest_path.name} : {detail}")
                        last_log_time = now
        except (AssertionError, AttributeError):
            # curl_cffi raises AssertionError if stream=True was not specified on initial request
            raw = getattr(response, "content", b"") or b""
            chunk_size = 65536
            for i in range(0, len(raw), chunk_size):
                chunk = raw[i : i + chunk_size]
                f.write(chunk)
                downloaded += len(chunk)
                now = time.time()
                pct, detail = _calc_progress()

                if progress_callback and (now - last_ui_time >= 0.2):
                    progress_callback(pct, f"{phase_label} en cours...", detail)
                    last_ui_time = now

    size_mb = dest_path.stat().st_size / (1024 * 1024)
    logger.info(f"Fichier téléchargé avec succès : {dest_path.name} ({size_mb:.2f} Mo).")
    return True, str(dest_path)
