"""Entités du domaine Compte et Session Utilisateur."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class AccountSessionEntity:
    """Entité métier pure représentant la session authentifiée d'un provider."""

    provider_name: str
    is_authenticated: bool = False
    user_display_name: str = ""
    cookies_data: dict[str, str] = field(default_factory=dict)
    user_agent: str = ""
    last_verified: Optional[datetime] = None
