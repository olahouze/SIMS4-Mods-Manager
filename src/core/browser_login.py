"""
Interactive browser management and Playwright automation helper for logins,
age gates, and Cloudflare clearance.
"""

import os
import time
from pathlib import Path
from typing import Optional, Dict, Tuple

from src.core.config import AppConfig
from src.utils.logger import logger


class BrowserLoginHelper:
    """Helper for checking browser availability and executing interactive Playwright logins."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    _browser_available_cached: Optional[bool] = None

    @classmethod
    def is_browser_available(cls) -> bool:
        """
        Checks if a browser engine (Chromium, Edge or Chrome) is available for Playwright.
        Uses fast filesystem checks and caches the result to prevent slow Chromium launches on startup.
        """
        if cls._browser_available_cached is not None:
            return cls._browser_available_cached

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

        pw_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        if pw_dir.exists() and any(pw_dir.glob("chromium*")):
            cls._browser_available_cached = True
            return True

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
        save_session_callback,
        user_agent: Optional[str] = None,
        timeout_seconds: int = 180,
    ) -> Tuple[bool, str, Dict[str, str]]:
        """
        Launches a visible Chromium/Edge window via Playwright to let the user log in or solve Cloudflare.
        Captures cookies and invokes save_session_callback once verified.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return False, "Playwright n'est pas installé dans l'environnement.", {}

        effective_ua = user_agent or cls.DEFAULT_USER_AGENT
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

            for ch in channels_to_try:
                try:
                    kwargs = {
                        "user_data_dir": str(profile_dir),
                        "headless": False,
                        "args": launch_args,
                        "user_agent": effective_ua,
                        "viewport": None,
                    }
                    if ch:
                        kwargs["channel"] = ch
                    context = p.chromium.launch_persistent_context(**kwargs)  # type: ignore[arg-type]
                    logger.info(f"Navigateur ouvert avec succès (moteur={ch or 'playwright-chromium'}).")
                    break
                except Exception as e:
                    logger.warning(f"Échec du lancement avec le canal {ch}: {e}")

            if context is None:
                from src.infrastructure.network.browser_updater_service import BrowserUpdaterService

                logger.info("Tentative d'installation automatique de Chromium pour Playwright...")
                ok_install, install_msg = BrowserUpdaterService.install_chromium_stream()
                if ok_install:
                    cls._browser_available_cached = True
                    try:
                        kwargs = {
                            "user_data_dir": str(profile_dir),
                            "headless": False,
                            "args": launch_args,
                            "user_agent": effective_ua,
                            "viewport": None,
                        }
                        context = p.chromium.launch_persistent_context(**kwargs)  # type: ignore[arg-type]
                        logger.info("Navigateur ouvert avec succès après installation de Chromium.")
                    except Exception as e:
                        return False, f"Impossible de lancer le navigateur après installation (Erreur: {e}).", {}
                else:
                    return (
                        False,
                        f"Impossible de lancer le navigateur et échec du téléchargement de Chromium ({install_msg}).",
                        {},
                    )

            page = context.pages[0] if context.pages else context.new_page()

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

            start_time = time.time()
            while time.time() - start_time < timeout_seconds:
                try:
                    if page.is_closed() or not context.pages:
                        break

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

            try:
                raw_cookies = context.cookies()
                for c in raw_cookies:
                    cookies_dict[c["name"]] = c["value"]
                logger.info(f"Extraction réussie de {len(cookies_dict)} cookie(s) depuis le navigateur.")
            except Exception as e:
                logger.error(f"Erreur lors de l'extraction des cookies: {e}")

            context.close()

        if cookies_dict:
            if provider_name == "loverslab":
                if cookies_dict.get("ips4_member_id") and cookies_dict.get("ips4_member_id") != "0":
                    is_authenticated = True
                elif "cf_clearance" in cookies_dict or "ips4_hasAcceptedAge" in cookies_dict:
                    is_authenticated = True

            save_session_callback(
                provider_name=provider_name,
                cookies=cookies_dict,
                user_display_name=display_name,
                is_authenticated=is_authenticated,
                user_agent=effective_ua,
            )
            return True, f"Session enregistrée pour {provider_name} ({len(cookies_dict)} cookies).", cookies_dict
        return False, "Aucun cookie récupéré.", {}
