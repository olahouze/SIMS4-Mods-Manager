import hashlib
import mimetypes
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from src.core.config import AppConfig


def hash_url(url: str) -> str:
    """Returns a deterministic MD5 hex digest for an image or resource URL."""
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def infer_extension(url: str, content_type: Optional[str] = None) -> str:
    """
    Infers a file extension (.jpg, .png, .webp, etc.) from an URL or HTTP Content-Type header.
    Defaults to .jpg if unknown.
    """
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            if ext == ".jpe":
                return ".jpg"
            return ext

    parsed_path = urlparse(url).path
    suffix = Path(parsed_path).suffix.lower()
    if suffix in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]:
        return ".jpg" if suffix == ".jpeg" else suffix

    return ".jpg"


def get_cached_image_path(url: str, cache_type: str = "images") -> Path:
    """
    Resolves the standardized local filesystem path for a cached image URL.
    `cache_type` can be 'thumbnails', 'images', 'screenshots', or 'desc_images'.
    """
    u_hash = hash_url(url)
    ext = infer_extension(url)

    if cache_type == "thumbnails":
        base_dir = AppConfig.get_thumbnails_cache_dir()
    elif cache_type == "screenshots":
        base_dir = AppConfig.get_screenshots_cache_dir()
    elif cache_type == "desc_images":
        base_dir = AppConfig.get_desc_images_cache_dir()
    else:
        base_dir = AppConfig.get_images_cache_dir()

    return base_dir / f"{u_hash}{ext}"
