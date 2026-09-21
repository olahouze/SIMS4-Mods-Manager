"""Routes API REST pour les comptes et sessions anti-bot (Front -> Back)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.schemas.accounts import (
    AccountActionResponse,
    AccountListResponse,
    AccountLoginRequest,
    AccountLoginResponse,
    AccountStatusItem,
)
from src.core.session_manager import SessionManager
from src.infrastructure.database.repositories.sqlalchemy_account_repository import (
    SqlAlchemyAccountRepository,
)

router = APIRouter(prefix="/accounts", tags=["Accounts & Anti-Bot"])
_account_repo = SqlAlchemyAccountRepository()

PROVIDERS_LOGIN_URLS = {
    "loverslab": "https://www.loverslab.com/login/",
    "patreon": "https://www.patreon.com/login",
}


@router.get("", response_model=AccountListResponse)
def get_accounts() -> AccountListResponse:
    """Liste le statut d'authentification et anti-bot de tous les providers supportés."""
    accounts_list: list[AccountStatusItem] = []

    for p_name in ["loverslab", "patreon"]:
        acc = _account_repo.get_by_provider(p_name)
        is_ready = SessionManager.is_session_ready(p_name)
        is_member = SessionManager.is_member_authenticated(p_name)
        cookies_dict = acc.cookies_data if acc else {}

        user_display_name = ""
        if acc and acc.user_display_name:
            user_display_name = acc.user_display_name
        elif is_member:
            user_display_name = "Connecté"
        elif is_ready:
            user_display_name = "Anti-bot validé"

        accounts_list.append(
            AccountStatusItem(
                provider_name=p_name,
                is_configured=acc is not None and len(cookies_dict) > 0,
                is_ready=is_ready,
                is_member=is_member,
                user_display_name=user_display_name,
                cookies_count=len(cookies_dict),
                last_verified=acc.last_verified if acc else None,
            )
        )

    return AccountListResponse(accounts=accounts_list)


@router.post("/{provider_name}/test", response_model=AccountActionResponse)
def test_account(provider_name: str) -> AccountActionResponse:
    """Effectue un test HTTP en direct des cookies de session pour le provider spécifié."""
    p_lower = provider_name.lower()
    if p_lower not in ["loverslab", "patreon"]:
        raise HTTPException(status_code=400, detail=f"Fournisseur non reconnu: {provider_name}")

    ok, msg = SessionManager.verify_session(p_lower)
    return AccountActionResponse(success=ok, message=msg)


@router.delete("/{provider_name}", response_model=AccountActionResponse)
def clear_account(provider_name: str) -> AccountActionResponse:
    """Efface les cookies de session stockés et supprime le profil de navigateur persistant."""
    p_lower = provider_name.lower()
    if p_lower not in ["loverslab", "patreon"]:
        raise HTTPException(status_code=400, detail=f"Fournisseur non reconnu: {provider_name}")

    ok = SessionManager.clear_session(p_lower)
    if ok:
        return AccountActionResponse(success=True, message=f"Session pour '{provider_name}' réinitialisée avec succès.")
    return AccountActionResponse(
        success=False, message=f"Erreur lors de la réinitialisation de la session pour '{provider_name}'."
    )


@router.post("/{provider_name}/login", response_model=AccountLoginResponse)
def login_account(provider_name: str, payload: AccountLoginRequest = AccountLoginRequest()) -> AccountLoginResponse:
    """Lance une fenêtre Playwright interactive pour résoudre Cloudflare ou se connecter."""
    p_lower = provider_name.lower()
    if p_lower not in PROVIDERS_LOGIN_URLS:
        raise HTTPException(status_code=400, detail=f"Fournisseur non reconnu: {provider_name}")

    login_url = PROVIDERS_LOGIN_URLS[p_lower]
    ok, msg, cookies = SessionManager.launch_interactive_login(
        provider_name=p_lower,
        target_url=login_url,
        timeout_seconds=payload.timeout_seconds,
    )

    return AccountLoginResponse(
        success=ok,
        message=msg,
        cookies_count=len(cookies),
    )
