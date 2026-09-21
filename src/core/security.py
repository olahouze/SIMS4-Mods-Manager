"""Gestionnaire de sécurité et d'authentification par jeton pour l'API locale."""

import hmac
import os
import secrets
from typing import Optional

from src.utils.logger import logger

_internal_token: Optional[str] = None
_auth_disabled: bool = False


def init_security(disable_auth: bool = False) -> str:
    """Initialise le sous-système de sécurité de l'API locale.

    Args:
        disable_auth: Si True, désactive la vérification du jeton (réservé aux tests/simulations).

    Returns:
        Le jeton de sécurité actif (ou une chaîne vide si désactivé).
    """
    global _internal_token, _auth_disabled

    env_disable = os.environ.get("SIMS4_DISABLE_AUTH", "").lower() in ("1", "true", "yes")
    if disable_auth or env_disable:
        _auth_disabled = True
        _internal_token = None
        logger.warning("[SÉCURITÉ] Authentification par jeton interne DÉSACTIVÉE (Mode Test/Simulation).")
        return ""

    _auth_disabled = False
    env_token = os.environ.get("SIMS4_INTERNAL_TOKEN")
    if env_token and len(env_token.strip()) >= 16:
        _internal_token = env_token.strip()
    else:
        _internal_token = secrets.token_urlsafe(32)

    logger.info("[SÉCURITÉ] Jeton de session interne généré et actif en mémoire pure.")
    return _internal_token


def get_internal_token() -> Optional[str]:
    """Retourne le jeton de sécurité interne actuellement actif."""
    return _internal_token


def is_auth_disabled() -> bool:
    """Indique si l'authentification par jeton est désactivée."""
    return _auth_disabled or os.environ.get("SIMS4_DISABLE_AUTH", "").lower() in ("1", "true", "yes")


def verify_internal_token(provided_token: Optional[str]) -> bool:
    """Vérifie la validité d'un jeton reçu avec protection contre les attaques par canal auxiliaire.

    Args:
        provided_token: Le jeton extrait de l'en-tête X-Internal-Token.

    Returns:
        True si l'authentification est valide ou désactivée, False sinon.
    """
    if is_auth_disabled():
        return True

    if _internal_token is None:
        # Si la sécurité n'a pas été explicitement initialisée (ex: tests unitaires rapides)
        return True

    if not provided_token:
        return False

    return hmac.compare_digest(provided_token.strip(), _internal_token)
