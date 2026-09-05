import os
import time
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple
from curl_cffi import requests as cffi_requests

from src.core.config import AppConfig
from src.database import DatabaseManager, AccountSession
from src.utils.logger import logger


class SessionManager:
    """
    Manages Playwright persistent browser profiles, interactive logins for Cloudflare/Auth/NSFW,
    session verification, cookie persistence, and impersonated curl_cffi HTTP sessions.
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    _http_sessions: Dict[str, cffi_requests.Session] = {}
    _http_sessions_lock: threading.Lock = threading.Lock()

    @classmethod
    def invalidate_http_session(cls, provider_name: str) -> None:
        """Closes and removes the pooled HTTP session for a provider."""
        with cls._http_sessions_lock:
            old_sess = cls._http_sessions.pop(provider_name.lower(), None)
            if old_sess:
                try:
                    old_sess.close()
                except Exception:
                    pass

    @classmethod
    def close_all_http_sessions(cls) -> None:
        """Closes all pooled curl_cffi sessions."""
        with cls._http_sessions_lock:
            for s in cls._http_sessions.values():
                try:
                    s.close()
                except Exception:
                    pass
            cls._http_sessions.clear()

    @classmethod
    def get_saved_session(cls, provider_name: str) -> Optional[AccountSession]:
        """Retrieves stored session info from SQLite."""
        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            return session.query(AccountSession).filter_by(provider_name=provider_name).first()

    @classmethod
    def is_member_authenticated(cls, provider_name: str) -> bool:
        """
        Checks if the user is authenticated with an actual registered member account.
        (Distinct from a guest session with anti-bot cookies only).
        """
        acc = cls.get_saved_session(provider_name)
        if not acc:
            return False
        cookies = acc.get_cookies_dict()
        if not cookies:
            return False

        if provider_name.lower() == "loverslab":
            member_id = cookies.get("ips4_member_id")
            return bool(member_id and member_id != "0")

        if provider_name.lower() == "patreon":
            return bool(cookies.get("session_id") or cookies.get("patreon_session_id") or cookies.get("api_session_id"))

        return acc.is_authenticated

    @classmethod
    def is_session_ready(cls, provider_name: str) -> bool:
        """
        Checks if the provider session has valid cookies/tokens to navigate and download.
        For LoversLab: accepts cf_clearance, ips4_hasAcceptedAge, or member login.
        For Patreon: accepts session cookies.
        """
        acc = cls.get_saved_session(provider_name)
        if not acc:
            return False

        cookies = acc.get_cookies_dict()
        if not cookies:
            return False

        if provider_name.lower() == "loverslab":
            # Ready if we have Cloudflare clearance, adult age consent, or member login
            has_cf = bool(cookies.get("cf_clearance"))
            has_age = bool(cookies.get("ips4_hasAcceptedAge"))
            has_member = bool(cookies.get("ips4_member_id") and cookies.get("ips4_member_id") != "0")
            has_session = bool(cookies.get("ips4_IPSSessionFront"))
            return has_cf or has_age or has_member or has_session

        if provider_name.lower() == "patreon":
            return bool(
                cookies.get("session_id")
                or cookies.get("patreon_session_id")
                or cookies.get("api_session_id")
                or len(cookies) >= 2
            )

        return len(cookies) > 0

    @classmethod
    def save_session(
        cls,
        provider_name: str,
        cookies: Dict[str, str],
        user_display_name: str = "",
        is_authenticated: bool = True,
        user_agent: Optional[str] = None,
    ) -> None:
        """Stores or updates session data in SQLite with detailed token analysis."""
        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            acc = session.query(AccountSession).filter_by(provider_name=provider_name).first()

            # Check for member ID or display name in cookies
            member_id = cookies.get("ips4_member_id")
            if member_id and member_id != "0" and not user_display_name:
                user_display_name = f"Membre #{member_id}"

            if not acc:
                acc = AccountSession(
                    provider_name=provider_name,
                    is_authenticated=is_authenticated,
                    user_display_name=user_display_name,
                    user_agent=user_agent or cls.DEFAULT_USER_AGENT,
                    last_verified=datetime.now(),
                )
                acc.set_cookies_dict(cookies)
                session.add(acc)
            else:
                acc.is_authenticated = is_authenticated
                if user_display_name:
                    acc.user_display_name = user_display_name
                if user_agent:
                    acc.user_agent = user_agent
                acc.set_cookies_dict(cookies)
                acc.last_verified = datetime.now()
            session.commit()

            tokens_found = [
                k for k in ["cf_clearance", "ips4_hasAcceptedAge", "ips4_member_id", "session_id"] if k in cookies
            ]
            cls.invalidate_http_session(provider_name)
            logger.info(
                f"Session enregistrée pour '{provider_name}': {len(cookies)} cookie(s) sauvegardé(s). "
                f"Tokens identifiés: {tokens_found}. Utilisateur: '{user_display_name or 'Anonyme/Anti-bot validé'}'."
            )

    @classmethod
    def clear_session(cls, provider_name: str) -> bool:
        """Clears stored session from SQLite and removes persistent browser profile directory."""
        try:
            cls.invalidate_http_session(provider_name)
            db = DatabaseManager.get_instance()
            with db.get_session() as session:
                acc = session.query(AccountSession).filter_by(provider_name=provider_name).first()
                if acc:
                    session.delete(acc)
                    session.commit()

            # Clean browser profile folder
            profile_dir = AppConfig.get_browser_profile_dir() / provider_name
            if profile_dir.exists():
                shutil.rmtree(profile_dir, ignore_errors=True)

            logger.info(f"Session et profil navigateur réinitialisés pour '{provider_name}'.")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la réinitialisation de session pour '{provider_name}': {e}")
            return False

    @classmethod
    def verify_session(cls, provider_name: str) -> Tuple[bool, str]:
        """Performs a live HTTP check using saved cookies and updates status."""
        session = cls.get_http_session(provider_name)
        try:
            if provider_name.lower() == "loverslab":
                url = "https://www.loverslab.com/"
                resp = session.get(url, timeout=12)
                logger.info(f"Test de session LoversLab ({url}) -> Code HTTP {resp.status_code}")
                if resp.status_code == 200:
                    html = resp.text
                    if "elUserNav" in html or "Sign Out" in html or "Déconnexion" in html:
                        return True, "Session membre connectée et active."
                    elif "cf_clearance" in str(session.cookies) or "ips4_hasAcceptedAge" in str(session.cookies):
                        return True, "Session active (Anti-Bot Cloudflare & +18 ans validés)."
                    return True, "Accès au site vérifié avec succès."
                elif resp.status_code in [403, 503]:
                    return (
                        False,
                        f"Protection Cloudflare active (Code {resp.status_code}). Veuillez rouvrir le navigateur.",
                    )

            elif provider_name.lower() == "patreon":
                url = "https://www.patreon.com/api/current_user"
                resp = session.get(url, timeout=12)
                logger.info(f"Test de session Patreon ({url}) -> Code HTTP {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json().get("data", {}).get("attributes", {})
                    name = data.get("full_name") or data.get("email") or "Connecté"
                    return True, f"Connecté à Patreon ({name})."
                elif resp.status_code in [401, 403]:
                    return False, "Non connecté à Patreon ou session expirée."

            return False, f"Réponse inattendue (Code {resp.status_code})"
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de session pour {provider_name}: {e}")
            return False, f"Erreur de connexion: {e}"

    @classmethod
    def get_http_session(cls, provider_name: str, force_new: bool = False) -> cffi_requests.Session:
        """
        Returns a configured curl_cffi Session loaded with provider cookies and browser impersonation.
        Reuses pooled session per provider for connection reuse and performance.
        """
        key = provider_name.lower()
        if not force_new:
            with cls._http_sessions_lock:
                if key in cls._http_sessions:
                    return cls._http_sessions[key]

        http_session = cffi_requests.Session(impersonate="chrome120")
        http_session.headers.update(
            {
                "User-Agent": cls.DEFAULT_USER_AGENT,
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

        # Load cookies from DB
        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            acc = session.query(AccountSession).filter_by(provider_name=provider_name).first()
            if acc:
                cookies = acc.get_cookies_dict()
                for name, value in cookies.items():
                    http_session.cookies.set(name, value)
                if acc.user_agent:
                    http_session.headers["User-Agent"] = acc.user_agent

        # For LoversLab: automatically ensure adult age consent cookie
        if key == "loverslab":
            http_session.cookies.set("ips4_hasAcceptedAge", "1", domain=".loverslab.com")
            http_session.cookies.set("ips4_IPSSessionFront", "1", domain=".loverslab.com")

        if not force_new:
            with cls._http_sessions_lock:
                cls._http_sessions[key] = http_session

        return http_session

    _browser_available_cached: Optional[bool] = None

    @classmethod
    def is_browser_available(cls) -> bool:
        """
        Checks if a browser engine (Chromium, Edge or Chrome) is available for Playwright.
        Uses fast filesystem checks and caches the result to prevent slow Chromium launches on startup.
        """
        if cls._browser_available_cached is not None:
            return cls._browser_available_cached

        # Fast check 1: System Microsoft Edge or Google Chrome executables
        candidates = [
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
            / r"Microsoft\Edge\Application\msedge.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / r"Microsoft\Edge\Application\msedge.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / r"Google\Chrome\Application\chrome.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
            / r"Google\Chrome\Application\chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / r"Google\Chrome\Application\chrome.exe",
        ]
        for c in candidates:
            if c.exists():
                cls._browser_available_cached = True
                return True

        # Fast check 2: Playwright installed browsers in %LOCALAPPDATA%\ms-playwright
        pw_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        if pw_dir.exists() and any(pw_dir.glob("chromium*")):
            cls._browser_available_cached = True
            return True

        # Fallback: Actual launch test once
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                for ch in [None, "msedge", "chrome"]:
                    try:
                        b = p.chromium.launch(headless=True, channel=ch)
                        b.close()
                        cls._browser_available_cached = True
                        return True
                    except Exception:
                        continue
            cls._browser_available_cached = False
            return False
        except Exception:
            cls._browser_available_cached = False
            return False

    @classmethod
    def launch_interactive_login(
        cls,
        provider_name: str,
        target_url: str,
        success_indicator_selector: Optional[str] = None,
        timeout_seconds: int = 180,
    ) -> Tuple[bool, str, Dict[str, str]]:
        """
        Launches a visible Chromium/Edge window via Playwright to let the user log in or solve Cloudflare.
        Captures cookies and saves session once closed or verified.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return False, "Playwright n'est pas installé dans l'environnement.", {}

        profile_dir = AppConfig.get_browser_profile_dir() / provider_name
        profile_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Lancement du navigateur interactif pour '{provider_name}' à l'adresse: {target_url}...")

        cookies_dict: Dict[str, str] = {}
        display_name = ""
        is_authenticated = False

        with sync_playwright() as p:
            context = None
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ]

            channels_to_try = [None, "msedge", "chrome"]
            last_err = None

            for ch in channels_to_try:
                try:
                    kwargs = {
                        "user_data_dir": str(profile_dir),
                        "headless": False,
                        "args": launch_args,
                        "user_agent": cls.DEFAULT_USER_AGENT,
                        "viewport": None,
                    }
                    if ch:
                        kwargs["channel"] = ch
                    context = p.chromium.launch_persistent_context(**kwargs)
                    logger.info(f"Navigateur ouvert avec succès (moteur={ch or 'playwright-chromium'}).")
                    break
                except Exception as e:
                    last_err = e
                    logger.warning(f"Échec du lancement avec le canal {ch}: {e}")

            if context is None:
                return False, f"Impossible de lancer le navigateur (Erreur: {last_err}).", {}

            # Reuse existing page to prevent a 2nd window with about:blank
            page = context.pages[0] if context.pages else context.new_page()

            # Set adult consent cookie for LoversLab
            if "loverslab.com" in target_url:
                context.add_cookies(
                    [
                        {
                            "name": "ips4_hasAcceptedAge",
                            "value": "1",
                            "domain": ".loverslab.com",
                            "path": "/",
                        }
                    ]
                )

            try:
                page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
            except Exception as e:
                logger.warning(f"Avertissement lors de la navigation initiale: {e}")

            logger.info(
                "Fenêtre ouverte. En attente de vos actions (Cloudflare, connexion, consentement) ou fermeture..."
            )

            # Wait loop while the browser window is open
            start_time = time.time()
            while time.time() - start_time < timeout_seconds:
                try:
                    if page.is_closed() or not context.pages:
                        break

                    # Check for login indicators
                    if provider_name == "loverslab":
                        if (
                            page.query_selector("#elUserNav")
                            or page.query_selector("a#elUserLink")
                            or page.query_selector("[data-action='signOut']")
                        ):
                            is_authenticated = True
                            user_elem = page.query_selector("a#elUserLink") or page.query_selector("#elUserNav strong")
                            if user_elem:
                                display_name = user_elem.inner_text().strip()
                    elif provider_name == "patreon":
                        if page.query_selector("[data-tag='user-menu-btn']") or page.query_selector(
                            "nav[aria-label='User']"
                        ):
                            is_authenticated = True

                    time.sleep(1.0)
                except Exception:
                    break

            # Capture all cookies from context
            try:
                raw_cookies = context.cookies()
                for c in raw_cookies:
                    cookies_dict[c["name"]] = c["value"]
                logger.info(f"Extraction réussie de {len(cookies_dict)} cookie(s) depuis le navigateur.")
            except Exception as e:
                logger.error(f"Erreur lors de l'extraction des cookies: {e}")

            context.close()

        if cookies_dict:
            # Check if cookies indicate valid session even without selector hit
            if provider_name == "loverslab":
                if cookies_dict.get("ips4_member_id") and cookies_dict.get("ips4_member_id") != "0":
                    is_authenticated = True
                elif "cf_clearance" in cookies_dict or "ips4_hasAcceptedAge" in cookies_dict:
                    # Valid anti-bot session
                    is_authenticated = True

            cls.save_session(
                provider_name=provider_name,
                cookies=cookies_dict,
                user_display_name=display_name,
                is_authenticated=is_authenticated,
                user_agent=cls.DEFAULT_USER_AGENT,
            )
            return True, f"Session enregistrée pour {provider_name} ({len(cookies_dict)} cookies).", cookies_dict
        else:
            return False, "Aucun cookie récupéré.", {}
