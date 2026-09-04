import zipfile
from pathlib import Path
from typing import List
from src.utils.logger import logger


def is_archive(file_path: Path) -> bool:
    """Checks whether the file is a valid supported archive (zip, rar, 7z)."""
    if not file_path.exists() or file_path.stat().st_size == 0:
        return False

    # Instant check for Sims 4 DBPF package files (never an archive)
    try:
        with open(file_path, "rb") as f:
            magic = f.read(4)
        if magic == b"DBPF":
            return False
    except Exception:
        pass

    suffix = file_path.suffix.lower()
    if suffix == ".zip" or zipfile.is_zipfile(file_path):
        return zipfile.is_zipfile(file_path)

    if suffix == ".7z":
        try:
            import py7zr

            return py7zr.is_7zfile(file_path)
        except Exception:
            return False

    if suffix == ".rar":
        try:
            import rarfile

            return rarfile.is_rarfile(file_path)
        except Exception:
            return False

    return False


def extract_archive(archive_path: Path, dest_dir: Path) -> List[Path]:
    """
    Extracts an archive (zip, rar, 7z) into dest_dir and returns the list of extracted files.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = archive_path.suffix.lower()
    extracted_files: List[Path] = []

    if suffix == ".zip":
        with zipfile.ZipFile(archive_path, "r") as z:
            z.extractall(dest_dir)
    elif suffix == ".7z":
        try:
            import py7zr

            with py7zr.SevenZipFile(archive_path, mode="r") as z:
                z.extractall(path=dest_dir)
        except Exception as e:
            logger.error(f"Failed to extract 7z archive {archive_path}: {e}")
            raise
    elif suffix == ".rar":
        try:
            import rarfile

            with rarfile.RarFile(archive_path) as rf:
                rf.extractall(dest_dir)
        except Exception as e:
            logger.error(f"Failed to extract RAR archive {archive_path}: {e}")
            raise
    else:
        raise ValueError(f"Unsupported archive format: {suffix}")

    for p in dest_dir.rglob("*"):
        if p.is_file():
            extracted_files.append(p)

    return extracted_files


def create_backup_zip(source_dir: Path, backup_zip_path: Path) -> Path:
    """Creates a zip archive of the given folder for backup."""
    backup_zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(backup_zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(source_dir)
                z.write(file_path, arcname)
    return backup_zip_path
