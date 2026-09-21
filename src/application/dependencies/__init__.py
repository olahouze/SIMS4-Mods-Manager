"""Domaine applicatif de résolution des dépendances et rapports de prérequis."""

from src.application.dependencies.dependency_resolver import resolve_mod_dependencies
from src.application.dependencies.requirement_reporter_service import RequirementReporterService

__all__ = ["resolve_mod_dependencies", "RequirementReporterService"]
