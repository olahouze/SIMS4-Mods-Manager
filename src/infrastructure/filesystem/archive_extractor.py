"""Gestionnaire orienté objet d'archives (ZIP, RAR, 7Z).

Implémente le pattern Strategy pour chaque format avec détection automatique
des signatures de fichiers, extraction sécurisée et création de sauvegardes.
"""

from __future__ import annotations

import zipfile
from abc import ABC, abstractmethod
from pathlib import Path

from src.utils.logger import logger


class BaseArchiveHandler(ABC):
    """Interface abstraite pour un gestionnaire de format d'archive."""

    @abstractmethod
    def can_handle(self, path: Path) -> bool:
        """Détermine si le fichier correspond à ce format."""
        ...

    @abstractmethod
    def extract(self, path: Path, dest_dir: Path) -> list[Path]:
        """Extrait l'archive dans le répertoire cible et retourne la liste des fichiers."""
        ...


class ZipArchiveHandler(BaseArchiveHandler):
    """Gestionnaire des archives standard ZIP."""

    def can_handle(self, path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            with open(path, "rb") as f:
                header = f.read(4)
            if header.startswith(b"PK"):
                return zipfile.is_zipfile(path)
        except Exception:
            pass
        if path.suffix.lower() == ".zip":
            try:
                return zipfile.is_zipfile(path)
            except Exception:
                return False
        return False

    def extract(self, path: Path, dest_dir: Path) -> list[Path]:
        with zipfile.ZipFile(path, "r") as z:
            try:
                z.extractall(dest_dir, filter="data")
            except TypeError:
                z.extractall(dest_dir)
        return [p for p in dest_dir.rglob("*") if p.is_file()]


class SevenZipArchiveHandler(BaseArchiveHandler):
    """Gestionnaire des archives 7Z via py7zr."""

    def can_handle(self, path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            with open(path, "rb") as f:
                header = f.read(6)
            if header.startswith(b"7z\xbc\xaf'\x1c"):
                return True
        except Exception:
            pass
        if path.suffix.lower() == ".7z":
            try:
                import py7zr

                return py7zr.is_7zfile(path)
            except Exception:
                return False
        return False

    def extract(self, path: Path, dest_dir: Path) -> list[Path]:
        import py7zr

        with py7zr.SevenZipFile(path, mode="r") as z:
            z.extractall(path=dest_dir)
        return [p for p in dest_dir.rglob("*") if p.is_file()]


class RarArchiveHandler(BaseArchiveHandler):
    """Gestionnaire des archives RAR via rarfile."""

    def can_handle(self, path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            with open(path, "rb") as f:
                header = f.read(7)
            if header.startswith(b"Rar!\x1a\x07"):
                return True
        except Exception:
            pass
        if path.suffix.lower() == ".rar":
            try:
                import rarfile

                return rarfile.is_rarfile(path)
            except Exception:
                return False
        return False

    def extract(self, path: Path, dest_dir: Path) -> list[Path]:
        import rarfile

        with rarfile.RarFile(path) as rf:
            rf.extractall(dest_dir)
        return [p for p in dest_dir.rglob("*") if p.is_file()]


class ArchiveExtractor:
    """Façade unifiée pour la détection et l'extraction d'archives tous formats."""

    def __init__(self) -> None:
        self._handlers: list[BaseArchiveHandler] = [
            ZipArchiveHandler(),
            SevenZipArchiveHandler(),
            RarArchiveHandler(),
        ]

    def is_archive(self, file_path: Path) -> bool:
        """Vérifie si le fichier est une archive supportée valide."""
        if not file_path.exists() or file_path.stat().st_size == 0:
            return False

        # Vérification immédiate de signature binaire pour éviter de confondre avec les packages Sims 4 DBPF
        try:
            with open(file_path, "rb") as f:
                magic = f.read(4)
            if magic == b"DBPF":
                return False
        except Exception as e:
            logger.debug(f"Erreur lors du test de signature DBPF sur {file_path}: {e}")

        return any(handler.can_handle(file_path) for handler in self._handlers)

    def extract(self, archive_path: Path, dest_dir: Path) -> list[Path]:
        """Extrait l'archive avec le gestionnaire adéquat avec mécanisme de repli."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []

        # 1. Tester les gestionnaires dont la signature correspond
        for handler in self._handlers:
            if handler.can_handle(archive_path):
                try:
                    return handler.extract(archive_path, dest_dir)
                except Exception as e:
                    logger.warning(
                        f"Échec de l'extraction avec {handler.__class__.__name__} sur {archive_path.name}: {e}"
                    )
                    errors.append(f"{handler.__class__.__name__}: {e}")

        # 2. Repli : tenter tous les gestionnaires au cas où la signature était atypique
        for handler in self._handlers:
            try:
                extracted = handler.extract(archive_path, dest_dir)
                if extracted:
                    logger.info(
                        f"Extraction réussie avec le gestionnaire de secours {handler.__class__.__name__} sur {archive_path.name}"
                    )
                    return extracted
            except Exception:
                continue

        error_detail = " | ".join(errors) if errors else "Format d'archive non supporté"
        raise ValueError(f"Impossible d'extraire l'archive '{archive_path.name}': {error_detail}")

    def create_backup(self, source_dir: Path, backup_zip_path: Path) -> Path:
        """Crée une archive ZIP de sauvegarde du répertoire source."""
        backup_zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(backup_zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir)
                    z.write(file_path, arcname)
        return backup_zip_path


# Instance singleton réutilisable
_default_extractor = ArchiveExtractor()


def is_archive(file_path: Path) -> bool:
    """Fonction globale pour compatibilité ascendante."""
    return _default_extractor.is_archive(file_path)


def extract_archive(archive_path: Path, dest_dir: Path) -> list[Path]:
    """Fonction globale pour compatibilité ascendante."""
    return _default_extractor.extract(archive_path, dest_dir)


def create_backup_zip(source_dir: Path, backup_zip_path: Path) -> Path:
    """Fonction globale pour compatibilité ascendante."""
    return _default_extractor.create_backup(source_dir, backup_zip_path)
