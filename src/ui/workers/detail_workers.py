"""
Workers d'arrière-plan (QThread) pour la vue détaillée d'un mod :
- Récupération asynchrone des métadonnées et prérequis (FetchDetailsWorker)
- Téléchargement et mise en cache parallèle des miniatures de la galerie (GalleryBatchWorker)
- Rétrocompatibilité unitaire (GalleryThumbWorker)
- Téléchargement et mise en cache des images inline HTML (DescriptionImageLoaderWorker)
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
from typing import Optional, List, Dict

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QPixmap

from src.api.client import get_api_client
from src.core.config import AppConfig
from src.core.session_manager import SessionManager
from src.ui.components.image_cache import ImageCache
from src.utils.cache_utils import hash_url, infer_extension
from src.utils.logger import logger


class FetchDetailsWorker(QThread):
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        mod_id: Optional[int],
        page_url: Optional[str],
        source: str,
        remote_id: str,
        load_id: int = 0,
    ):
        super().__init__()
        self.mod_id = mod_id
        self.page_url = page_url
        self.source = source
        self.remote_id = remote_id
        self.load_id = load_id

    def run(self):
        try:
            api_client = get_api_client()
            if self.mod_id:
                data = api_client.get_catalog_mod_details(self.mod_id)
            else:
                # Mod opened from 'InstalledView' or without catalog id
                found_id = None
                try:
                    if self.remote_id:
                        cat = api_client.get_catalog(search=self.remote_id, page_size=10)
                        for item in cat.get("items", []):
                            if str(item.get("remote_id")) == str(self.remote_id) and item.get("source") == self.source:
                                found_id = item.get("id")
                                break
                except Exception as e:
                    logger.debug(f"Could not find catalog id for installed mod #{self.remote_id}: {e}")

                if found_id:
                    data = api_client.get_catalog_mod_details(found_id)
                else:
                    chk = api_client.check_dependencies({
                        "source": self.source,
                        "remote_id": self.remote_id,
                        "page_url": self.page_url,
                    })
                    data = {
                        "source": self.source,
                        "remote_id": self.remote_id,
                        "requirements_text": chk.get("requirements_text"),
                        "requirements_status": chk.get("requirements_status", "NONE"),
                        "dependencies": chk.get("already_installed_dependencies", []) + chk.get("missing_dependencies", []),
                        "description": "",
                        "screenshots": [],
                    }
            self.finished.emit(data)
        except Exception as e:
            self.failed.emit(str(e))


class GalleryBatchWorker(QThread):
    """
    Worker d'arrière-plan optimisé pour charger l'ensemble des images de la galerie en parallèle :
    1. Vérification immédiate du cache mémoire (0 ms)
    2. Vérification immédiate du cache disque local (0 ms)
    3. Téléchargement concurrent via ThreadPoolExecutor(max_workers=4) réutilisant une session HTTP unique
    4. Annulation coopérative lors d'un changement de mod
    """
    thumb_ready = Signal(int, QPixmap)

    _PIXMAP_CACHE: Dict[str, QPixmap] = {}
    _MAX_CACHE_SIZE: int = 200

    def __init__(self, urls: List[str], cache_dir: Path, load_id: int = 0):
        super().__init__()
        self.urls = urls
        self.cache_dir = cache_dir
        self.load_id = load_id
        self._is_cancelled = False

    def cancel(self):
        """Signal d'annulation coopérative pour interrompre les téléchargements en attente."""
        self._is_cancelled = True

    def run(self):
        if not self.urls:
            return

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        to_download = []

        # Phase 1 : Rendu immédiat depuis le cache mémoire ou le cache disque local
        for idx, url in enumerate(self.urls):
            if self._is_cancelled:
                return

            cached_pix = ImageCache.get(url) or self._PIXMAP_CACHE.get(url)
            if cached_pix:
                self.thumb_ready.emit(idx, cached_pix)
                continue

            cached_path = self.cache_dir / f"thumb_{hash_url(url)}{infer_extension(url)}"

            if cached_path.exists() and cached_path.stat().st_size > 0:
                pix = QPixmap(str(cached_path))
                if not pix.isNull():
                    scaled = pix.scaled(
                        170,
                        110,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self._store_pixmap(url, scaled)
                    self.thumb_ready.emit(idx, scaled)
                    continue

            to_download.append((idx, url, cached_path))

        if not to_download or self._is_cancelled:
            return

        # Phase 2 : Téléchargement parallèle avec session HTTP mutualisée
        session = SessionManager.get_http_session("loverslab")

        def _fetch_one(item):
            if self._is_cancelled:
                return None
            idx, url, cached_path = item
            try:
                resp = session.get(url, timeout=15)
                if resp.status_code == 200 and len(resp.content) > 0:
                    with open(cached_path, "wb") as f:
                        f.write(resp.content)
                    return idx, url, cached_path
            except Exception as e:
                logger.debug(f"Erreur téléchargement miniature galerie {url}: {e}")
            return None

        with ThreadPoolExecutor(max_workers=4) as executor:
            for result in executor.map(_fetch_one, to_download):
                if self._is_cancelled:
                    break
                if result:
                    idx, url, cached_path = result
                    pix = QPixmap(str(cached_path))
                    if not pix.isNull():
                        scaled = pix.scaled(
                            170,
                            110,
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        self._store_pixmap(url, scaled)
                        self.thumb_ready.emit(idx, scaled)

    @classmethod
    def _store_pixmap(cls, url: str, pix: QPixmap):
        ImageCache.set(url, pix)
        if len(cls._PIXMAP_CACHE) >= cls._MAX_CACHE_SIZE:
            cls._PIXMAP_CACHE.pop(next(iter(cls._PIXMAP_CACHE)))
        cls._PIXMAP_CACHE[url] = pix


class GalleryThumbWorker(QThread):
    """Worker unitaire (rétrocompatibilité pour tests ou téléchargement ponctuel)."""
    thumb_ready = Signal(int, QPixmap)

    def __init__(self, index: int, url: str, cache_dir: Path):
        super().__init__()
        self.index = index
        self.url = url
        self.cache_dir = cache_dir

    def run(self):
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cached = self.cache_dir / f"thumb_{hash_url(self.url)}{infer_extension(self.url)}"

            if not cached.exists() or cached.stat().st_size == 0:
                session = SessionManager.get_http_session("loverslab")
                resp = session.get(self.url, timeout=15)
                if resp.status_code == 200 and len(resp.content) > 0:
                    with open(cached, "wb") as f:
                        f.write(resp.content)

            if cached.exists() and cached.stat().st_size > 0:
                pix = QPixmap(str(cached))
                if not pix.isNull():
                    scaled = pix.scaled(
                        170,
                        110,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.thumb_ready.emit(self.index, scaled)
        except Exception as e:
            logger.debug(f"Error loading gallery thumb {self.url}: {e}")


class DescriptionImageLoaderWorker(QThread):
    images_updated = Signal(str)

    def __init__(self, raw_html: str):
        super().__init__()
        self.raw_html = raw_html
        self.cache_dir = AppConfig.get_images_cache_dir()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        if not self.raw_html:
            return

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        img_urls = list(set(re.findall(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', self.raw_html)))
        if not img_urls:
            return

        url_to_local = {}
        to_fetch = []
        for u in img_urls:
            cached = self.cache_dir / f"img_{hash_url(u)}{infer_extension(u)}"
            if cached.exists() and cached.stat().st_size > 0:
                url_to_local[u] = cached.as_uri()
            else:
                to_fetch.append((u, cached))

        # First update with already cached images immediately
        if url_to_local:
            html = self.raw_html
            for remote_u, local_uri in url_to_local.items():
                html = html.replace(remote_u, local_uri)
            self.images_updated.emit(html)

        if not to_fetch or self._is_cancelled:
            return

        session = SessionManager.get_http_session("loverslab")

        def _fetch_one(item):
            if self._is_cancelled:
                return None
            remote_url, dest_path = item
            try:
                resp = session.get(remote_url, timeout=15)
                if resp.status_code == 200 and len(resp.content) > 0:
                    with open(dest_path, "wb") as f:
                        f.write(resp.content)
                    return remote_url, dest_path.as_uri()
            except Exception as e:
                logger.debug(f"Failed to fetch inline image {remote_url}: {e}")
            return None

        with ThreadPoolExecutor(max_workers=6) as executor:
            for result in executor.map(_fetch_one, to_fetch):
                if result:
                    url_to_local[result[0]] = result[1]

        if not self._is_cancelled and url_to_local:
            html = self.raw_html
            for remote_u, local_uri in url_to_local.items():
                html = html.replace(remote_u, local_uri)
            self.images_updated.emit(html)
