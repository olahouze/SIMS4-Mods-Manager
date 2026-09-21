"""Entités du domaine pour les dépendances et prérequis de mods."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DependencyRequirement:
    """Spécification d'une dépendance requise par un mod."""

    title: str
    is_dlc: bool = False
    dlc_code: Optional[str] = None
    url: Optional[str] = None
    is_installed: bool = False
    is_optional: bool = False
    classification: str = "MOD"  # MOD, COMMENT, DLC, BASE_GAME


@dataclass
class RequirementReportEntity:
    """Rapport d'analyse de conformité des dépendances pour un mod ou le catalogue."""

    mod_id: int
    mod_title: str
    status: str  # OK, MISSING_DEPENDENCIES, MISSING_DLC, UNKNOWN
    dependencies: list[DependencyRequirement] = field(default_factory=list)
    missing_count: int = 0
