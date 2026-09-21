"""Classe de base abstraite et utilitaires de streaming pour les téléchargeurs réseau."""

from __future__ import annotations

import hashlib
import shutil
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional, Tuple

from src.utils.logger import logger


class BaseDownloader(ABC):
    """Classe de base abstraite pour le téléchargement robuste de fichiers et d'archives."""

    @abstractmethod
    def download_mod_file(
        self,
        url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
        **kwargs,
    ) -> Tuple[bool, str]:
        """Télécharge un mod depuis une URL distante vers une destination locale."""
        ...

    @staticmethod
    def stream_to_file(
        response,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
        phase_label: str = "Téléchargement",
        chunk_size: int = 65536,
        compute_sha256: bool = True,
    ) -> Tuple[bool, str, Optional[str]]:
        """Écrit un flux HTTP vers le disque avec calcul de vitesse, progression et hash SHA-256.

        Args:
            response: La réponse HTTP (Requests, Curl-Cffi ou Httpx) avec stream=True.
            dest_path: Le chemin absolu du fichier cible.
            progress_callback: Callback optionnel recevant (pourcentage, libellé, détails vitesse/taille).
            phase_label: Préfixe affiché dans l'interface utilisateur.
            chunk_size: Taille des blocs de lecture en octets.
            compute_sha256: Si True, calcule simultanément l'empreinte cryptographique SHA-256.

        Returns:
            Tuple (succès, message d'état, hash_sha256_hex_ou_None).
        """
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        total_size = int(response.headers.get("Content-Length") or 0)

        # Vérification de l'espace disque disponible
        if total_size > 0:
            free_bytes = shutil.disk_usage(dest_path.parent).free
            if free_bytes < (total_size + 10 * 1024 * 1024):
                err = f"Espace disque insuffisant ({free_bytes // (1024 * 1024)} Mo disponibles, {total_size // (1024 * 1024)} Mo requis)."
                logger.error(err)
                return False, err, None

        downloaded = 0
        start_time = time.time()
        last_log_time = start_time
        sha256_hasher = hashlib.sha256() if compute_sha256 else None

        try:
            with open(dest_path, "wb") as f:
                if hasattr(response, "iter_content"):
                    chunk_iterator = response.iter_content(chunk_size=chunk_size)
                elif hasattr(response, "iter_bytes"):
                    chunk_iterator = response.iter_bytes(chunk_size=chunk_size)
                else:
                    data = response.content
                    f.write(data)
                    if sha256_hasher:
                        sha256_hasher.update(data)
                    return True, "Téléchargement terminé.", sha256_hasher.hexdigest() if sha256_hasher else None

                for chunk in chunk_iterator:
                    if not chunk:
                        continue
                    f.write(chunk)
                    if sha256_hasher:
                        sha256_hasher.update(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    elapsed = max(now - start_time, 0.001)
                    speed_mbps = (downloaded / elapsed) / (1024 * 1024)

                    if now - last_log_time >= 0.2:
                        last_log_time = now
                        if total_size > 0:
                            percent = min(int((downloaded / total_size) * 100), 100)
                            rem_bytes = max(total_size - downloaded, 0)
                            rem_sec = (rem_bytes / (downloaded / elapsed)) if downloaded > 0 else 0
                            eta_str = f"{int(rem_sec)}s restante(s)" if rem_sec < 3600 else f"{int(rem_sec / 60)}m"
                            detail_str = (
                                f"{downloaded // (1024 * 1024)} Mo / {total_size // (1024 * 1024)} Mo "
                                f"({speed_mbps:.1f} Mo/s) — {eta_str}"
                            )
                        else:
                            percent = -1
                            detail_str = f"{downloaded // (1024 * 1024)} Mo ({speed_mbps:.1f} Mo/s)"

                        if progress_callback:
                            progress_callback(percent, phase_label, detail_str)

            if total_size > 0 and downloaded < total_size:
                err = f"Téléchargement incomplet ({downloaded}/{total_size} octets)."
                logger.error(err)
                return False, err, None

            digest = sha256_hasher.hexdigest() if sha256_hasher else None
            return True, "Téléchargement terminé avec succès.", digest

        except Exception as e:
            logger.error(f"Erreur d'écriture durant le streaming de téléchargement : {e}")
            if dest_path.exists():
                try:
                    dest_path.unlink()
                except Exception:
                    pass
            return False, f"Erreur de flux réseau : {e}", None
