#!/usr/bin/env python3
"""
SIMS 4 Mods Manager - Script de simulation utilisateur (API REST & Audit Web)
Ce script simule de bout en bout le flux utilisateur en utilisant l'API REST de l'application :
1. Cycle de vie de l'API (détection / démarrage automatique en sous-processus / arrêt propre).
2. Authentification LoversLab autonome (récupération de session ou lancement de Playwright Chromium/Edge).
3. Déclenchement et suivi du scraping complet LoversLab via l'API.
4. Audit de cohérence en direct sur Internet pour chaque mod (seules les incohérences sont retenues).
5. Installation séquentielle des mods installables via l'API.
6. Parcours séquentiel des logs avec filtrage strict (élimination de [INFO] et [DEBUG], rétention exclusive des erreurs).
7. Génération d'un rapport complet Markdown dans scripts/rapports/.
"""

# ruff: noqa: E402
import argparse
import atexit
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# Ajout de la racine du projet dans sys.path pour les imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx

from src.api.client import ApiClient
from src.core.config import AppConfig
from src.core.session_manager import SessionManager
from src.database.manager import DatabaseManager
from src.database.models import CatalogMod

# Répertoires clés
SCRIPTS_DIR = Path(__file__).resolve().parent
REPORTS_DIR = SCRIPTS_DIR / "rapports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class SimulationRunner:
    """Orchestre la simulation utilisateur de bout en bout."""

    def __init__(
        self,
        api_url: str = "http://127.0.0.1:8000",
        max_pages: int = 1,
        max_installs: Optional[int] = None,
        skip_install: bool = False,
        force_login: bool = False,
        keep_installed: bool = False,
    ):
        self.api_url = api_url.rstrip("/")
        self.max_pages = max_pages
        self.max_installs = max_installs
        self.skip_install = skip_install
        self.force_login = force_login
        self.keep_installed = keep_installed

        self.server_process: Optional[subprocess.Popen] = None
        self.api_client: Optional[ApiClient] = None
        # Suivi de l'offset des logs et des mods directement téléchargeables
        self.initial_log_offset = 0
        log_file = AppConfig.get_logs_dir() / "app.log"
        if log_file.exists():
            try:
                self.initial_log_offset = log_file.stat().st_size
            except Exception:
                self.initial_log_offset = 0

        self.verified_downloadable_mods: List[Dict[str, Any]] = []
        self.installed_mod_ids_before: set[int] = set()
        self.cleanup_results: List[Dict[str, Any]] = []

        # Résultats pour le rapport final
        self.inconsistencies: List[Dict[str, Any]] = []
        self.installation_results: List[Dict[str, Any]] = []
        self.filtered_errors: List[str] = []
        self.stats: Dict[str, Any] = {
            "start_time": datetime.now(),
            "end_time": None,
            "total_catalog_mods": 0,
            "total_audited_mods": 0,
            "inconsistencies_count": 0,
            "installations_attempted": 0,
            "installations_succeeded": 0,
            "installations_failed": 0,
            "cleaned_mods_count": 0,
            "errors_logged_count": 0,
        }

    # =========================================================================
    # Étape 0 : Cycle de vie du serveur API
    # =========================================================================
    def ensure_api_server(self, force_restart: bool = False) -> None:
        """Vérifie si l'API est accessible, ou la lance/redémarre en arrière-plan."""
        if not force_restart and self._ping_api():
            if self.api_client is None:
                print(f"\n[ÉTAPE 0] Vérification de la disponibilité de l'API sur {self.api_url}...")
                print(" -> Serveur API déjà actif et réactif.")
                self.api_client = ApiClient(base_url=self.api_url)
            return

        print(f"\n[INFO] Initialisation / Redémarrage du serveur API sur {self.api_url}...")
        self._cleanup_server()

        parsed = urlparse(self.api_url)
        port = parsed.port or 8000
        host = parsed.hostname or "127.0.0.1"

        py_exe = sys.executable
        venv_py = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        if venv_py.exists():
            py_exe = str(venv_py)

        cmd = [py_exe, str(PROJECT_ROOT / "run.py"), "--server", "--port", str(port), "--host", host]
        self.server_process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        atexit.register(self._cleanup_server)

        # Attente active de la disponibilité du serveur
        max_attempts = 40
        for attempt in range(1, max_attempts + 1):
            time.sleep(0.5)
            if self._ping_api():
                print(f" -> Serveur API démarré avec succès (en {attempt * 0.5:.1f}s).")
                self.api_client = ApiClient(base_url=self.api_url)
                return

        raise RuntimeError(f"Impossible de démarrer ou joindre le serveur API sur {self.api_url} après 20s.")

    def call_api(self, method_name: str, *args, **kwargs) -> Any:
        """Exécute une méthode d'ApiClient avec reprise et redémarrage automatique en cas de déconnexion."""
        if not self.api_client:
            self.ensure_api_server()
        assert self.api_client is not None

        method = getattr(self.api_client, method_name)
        try:
            return method(*args, **kwargs)
        except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as e:
            print(f"\n [WARNING] Déconnexion ou indisponibilité API ({e}). Redémarrage automatique du serveur API...")
            self.ensure_api_server(force_restart=True)
            method = getattr(self.api_client, method_name)
            return method(*args, **kwargs)

    def _ping_api(self) -> bool:
        """Teste rapidement si l'API répond."""
        try:
            with httpx.Client(timeout=2.0) as c:
                resp = c.get(f"{self.api_url}/api/system/ping")
                if resp.status_code == 200:
                    return True
                # Fallback doc endpoint
                doc_resp = c.get(f"{self.api_url}/docs")
                return doc_resp.status_code == 200
        except Exception:
            return False

    def _cleanup_server(self) -> None:
        """Éteint proprement le serveur s'il a été lancé par le script."""
        if self.server_process and self.server_process.poll() is None:
            print("\n[INFO] Extinction propre du serveur API en arrière-plan...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            print(" -> Serveur API arrêté.")

    # =========================================================================
    # Étape 1 : Gestion des identifiants & session LoversLab
    # =========================================================================
    def setup_loverslab_session(self) -> None:
        """Récupère la session LoversLab ou lance l'authentification interactive Playwright."""
        print("\n[ÉTAPE 1] Vérification de la session LoversLab...")

        need_login = self.force_login
        if not need_login:
            if SessionManager.is_session_ready("loverslab"):
                print(" -> Session LoversLab trouvée en base de données locale. Vérification en cours...")
                ok, msg = SessionManager.verify_session("loverslab")
                if ok:
                    print(f" -> Session LoversLab valide : {msg}")
                else:
                    print(f" -> Session LoversLab invalide ou expirée ({msg}). Réauthentification requise.")
                    need_login = True
            else:
                print(" -> Aucune session LoversLab trouvée en base. Authentification requise.")
                need_login = True

        if need_login:
            print(" -> Lancement du navigateur Playwright pour connexion LoversLab / Cloudflare...")
            ok, msg, cookies = SessionManager.launch_interactive_login(
                provider_name="loverslab",
                target_url="https://www.loverslab.com/login/",
                timeout_seconds=180,
            )
            if not ok:
                print(f" [WARNING] Avertissement authentification LoversLab : {msg}")
            else:
                print(f" -> Connexion LoversLab réussie ! {len(cookies)} cookie(s) sauvegardé(s).")

        # Initialisation de la session curl_cffi pour les tests internet autonomes
        self.http_session = SessionManager.get_http_session("loverslab", force_new=True)
        print(" -> Session HTTP autonome (curl_cffi chrome120) prête pour l'audit.")

    # =========================================================================
    # Étape 2 : Lancement et attente du scraping complet LoversLab (API)
    # =========================================================================
    def sync_catalog(self) -> None:
        """Déclenche la synchronisation LoversLab via l'API et suit sa progression."""
        print("\n[ÉTAPE 2] Déclenchement de la synchronisation du catalogue LoversLab...")

        # Vérifier si une synchronisation est déjà active et la réinitialiser proprement
        status = self.call_api("get_catalog_sync_status")
        if status.get("is_running"):
            print(" -> Une synchronisation précédente était active. Arrêt et réinitialisation...")
            try:
                self.call_api("stop_catalog_sync")
                time.sleep(1.5)
            except Exception:
                pass

        page_desc = "TOUTES les pages" if self.max_pages <= 0 else f"{self.max_pages} page(s) par catégorie"
        print(f" -> Démarrage du scraping via POST /api/catalog/sync ({page_desc})...")
        start_resp = self.call_api("start_catalog_sync", max_pages=self.max_pages)
        print(f" -> Réponse API : {start_resp.get('message', 'Démarré')}")

        # Polling du statut jusqu'à achèvement
        last_pct = -1
        last_pages = -1
        last_scraped = -1
        while True:
            time.sleep(1.0)
            status = self.call_api("get_catalog_sync_status")
            is_running = status.get("is_running", False)
            pct = status.get("progress_percent", 0)
            msg = status.get("message", "")
            total_scraped = status.get("total_scraped", 0)
            pages = status.get("pages_completed", 0)
            total_pages = status.get("total_pages", 0)
            curr_cat = status.get("current_category", "")

            if pct != last_pct or pages != last_pages or total_scraped != last_scraped:
                cat_info = f" | {curr_cat}" if curr_cat else f" | {msg[:40]}"
                sys.stdout.write(
                    f"\r -> Progression : [{pct}%] - {pages}/{total_pages} pages | "
                    f"{total_scraped} mods répertoriés{cat_info}                              "
                )
                sys.stdout.flush()
                last_pct = pct
                last_pages = pages
                last_scraped = total_scraped

            if not is_running:
                print(f"\n -> Synchronisation terminée avec succès ! Total scraped : {total_scraped} mods.")
                break

    # =========================================================================
    # Étape 3 : Audit de cohérence Internet depuis le script
    # =========================================================================
    def audit_mods_consistency(self) -> None:
        """Parcourt les mods du catalogue et teste en direct sur Internet la cohérence."""
        print("\n[ÉTAPE 3] Audit de cohérence sur Internet pour chaque mod...")
        assert self.http_session is not None

        # 1. Récupération exhaustive de tous les mods via l'API
        all_mods: List[Dict[str, Any]] = []
        page = 1
        limit = 100

        print(" -> Récupération paginée des mods du catalogue via GET /api/catalog...")
        while True:
            resp = self.call_api("get_catalog", source="loverslab", page=page, limit=limit)
            items = resp.get("items", [])
            all_mods.extend(items)
            total = resp.get("total", len(all_mods))
            print(f"    Page {page} chargée ({len(all_mods)}/{total} mods)...")
            if len(all_mods) >= total or not items:
                break
            page += 1

        self.stats["total_catalog_mods"] = len(all_mods)
        print(f" -> Total de {len(all_mods)} mod(s) LoversLab à auditer.")

        # Accès direct à la DB pour avoir les détails bruts (download_urls, external_links)
        db = DatabaseManager.get_instance()
        db_mods_map: Dict[int, CatalogMod] = {}
        with db.get_session() as session:
            for cm in session.query(CatalogMod).filter_by(source="loverslab").all():
                db_mods_map[cm.id] = cm

        for idx, mod in enumerate(all_mods, start=1):
            mod_id = mod.get("id")
            title = mod.get("title", "Sans titre")
            page_url = mod.get("page_url", "")
            source = mod.get("source", "loverslab")
            remote_id = mod.get("remote_id") or (str(mod_id) if mod_id else "")
            patreon_status = mod.get("patreon_status", "NONE")
            cm_obj = db_mods_map.get(mod_id)

            safe_title_console = title[:40].encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8")
            try:
                sys.stdout.write(f"\r -> Audit [{idx}/{len(all_mods)}] : {safe_title_console}...                    ")
                sys.stdout.flush()
            except Exception:
                pass

            self.stats["total_audited_mods"] += 1

            # 3.1 Disponibilité de la page web
            page_ok, page_err = self._check_page_reachable(page_url)
            if not page_ok:
                self._record_inconsistency(
                    title=title,
                    url=page_url,
                    app_status="Répertorié dans le catalogue",
                    internet_status=f"Page inaccessible ({page_err})",
                    details="La page du mod LoversLab retourne une erreur ou a été supprimée.",
                )
                continue  # Pas de test plus poussé si la page est inaccessible

            # 3.2 Vérification du téléchargement direct LoversLab
            # Pour tous les mods LoversLab non-verrouillés, on vérifie si la page dispose d'un accès de téléchargement actif
            if source == "loverslab" and page_url and patreon_status != "LOCKED":
                dl_ok, dl_err = self._check_loverslab_direct_download(page_url)
                if dl_ok:
                    self.verified_downloadable_mods.append({
                        "id": mod_id,
                        "title": title,
                        "source": source,
                        "remote_id": remote_id,
                        "page_url": page_url,
                    })
                else:
                    # N'enregistrer une incohérence que si le mod revendiquait un téléchargement direct ou si la page échoue
                    has_explicit_direct = bool(cm_obj and cm_obj.get_download_urls_list())
                    if has_explicit_direct:
                        self._record_inconsistency(
                            title=title,
                            url=page_url,
                            app_status="Téléchargement direct LoversLab attendu",
                            internet_status=f"Échec téléchargement direct ({dl_err})",
                            details="Le lien de téléchargement direct /?do=download a échoué ou redirige vers une erreur/Patreon.",
                        )

            # 3.3 Cohérence du statut Patreon
            if patreon_status and patreon_status != "NONE":
                ext_links = cm_obj.get_external_links_list() if cm_obj else []
                patreon_link = next((link for link in ext_links if "patreon.com" in link.lower()), None)
                if patreon_link:
                    p_ok, p_actual, p_err = self._check_patreon_post_coherence(patreon_link, patreon_status)
                    if not p_ok:
                        self._record_inconsistency(
                            title=title,
                            url=patreon_link,
                            app_status=f"Statut Patreon : {patreon_status}",
                            internet_status=f"Réalité internet : {p_actual} ({p_err})",
                            details=f"Incohérence entre le statut enregistré ({patreon_status}) et le test direct Patreon.",
                        )

            # 3.4 Test des liens externes (Mega, Mediafire, Simfileshare...)
            if cm_obj:
                ext_links = cm_obj.get_external_links_list()
                for link in ext_links[:2]:  # Test des 2 premiers liens externes max
                    if "patreon.com" in link.lower():
                        continue
                    link_ok, link_err = self._check_external_link(link)
                    if not link_ok:
                        self._record_inconsistency(
                            title=title,
                            url=link,
                            app_status="Lien externe référencé",
                            internet_status=f"Lien mort / inaccessible ({link_err})",
                            details=f"Le lien d'hébergement externe ({link[:50]}) semble mort.",
                        )

        print(f"\n -> Audit terminé ! {len(self.inconsistencies)} incohérence(s) constatée(s).")
        self.stats["inconsistencies_count"] = len(self.inconsistencies)

    def _check_page_reachable(self, url: str) -> tuple[bool, str]:
        """Vérifie si l'URL LoversLab répond avec un code HTTP normal, avec réessai sur erreurs éphémères Cloudflare (520/5xx)."""
        if not url:
            return False, "URL vide"
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                assert self.http_session is not None
                resp = self.http_session.get(url, timeout=12, allow_redirects=True)
                if resp.status_code in [404, 410]:
                    return False, f"HTTP {resp.status_code}"
                if "The page you are looking for does not exist" in resp.text:
                    return False, "Page d'erreur LoversLab (contenu introuvable)"
                if resp.status_code in [520, 502, 503, 504, 429]:
                    if attempt < max_retries:
                        time.sleep(1.5)
                        continue
                    return True, f"Indisponibilité réseau temporaire Cloudflare (HTTP {resp.status_code})"
                if resp.status_code >= 400:
                    return False, f"HTTP {resp.status_code}"
                return True, ""
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(1.5)
                    continue
                return False, str(e)
        return True, ""

    def _check_loverslab_direct_download(self, page_url: str) -> tuple[bool, str]:
        """Simule l'accès au téléchargement direct LoversLab pour tester la validité."""
        assert self.http_session is not None
        dl_url = page_url.rstrip("/") + "/?do=download"
        try:
            # Effectue une requête GET sans télécharger le corps volumineux
            resp = self.http_session.get(dl_url, timeout=15, stream=True, allow_redirects=True)
            status = resp.status_code
            if status in [404, 410]:
                return False, f"HTTP {status} sur {dl_url}"
            if "patreon.com" in str(resp.url).lower():
                return False, f"Redirection inattendue vers Patreon ({resp.url})"
            if status == 403:
                return False, "Erreur 403 Forbidden (accès refusé ou captcha actif)"
            if status >= 400:
                return False, f"Code HTTP {status}"
            return True, ""
        except Exception as e:
            return False, str(e)

    def _check_patreon_post_coherence(self, patreon_url: str, app_status: str) -> tuple[bool, str, str]:
        """Vérifie si l'état réel d'un post Patreon concorde avec l'application."""
        assert self.http_session is not None
        try:
            resp = self.http_session.get(patreon_url, timeout=12, allow_redirects=True)
            if resp.status_code in [404, 410]:
                return False, "404_NOT_FOUND", f"Post Patreon supprimé ({resp.status_code})"

            text = resp.text.lower()
            is_locked = "unlock this post" in text or "join now to view" in text or "locked" in text
            actual = "LOCKED" if is_locked else "PUBLIC"

            if app_status in ["PUBLIC", "UNLOCKED"] and actual == "LOCKED":
                return False, "LOCKED", "Post verrouillé / payant sur Patreon alors que l'app l'indique PUBLIC"
            if app_status == "LOCKED" and actual == "PUBLIC":
                return False, "PUBLIC", "Post devenu public / déverrouillé sur Patreon alors que l'app l'indique LOCKED"

            return True, actual, ""
        except Exception as e:
            return True, "UNKNOWN", str(e)  # Pas d'incohérence si Patreon est simplement inaccessible

    def _check_external_link(self, url: str) -> tuple[bool, str]:
        """Teste rapidement un lien externe (Mega, Mediafire, etc.)."""
        assert self.http_session is not None
        try:
            resp = self.http_session.get(url, timeout=8, stream=True, allow_redirects=True)
            if resp.status_code in [404, 410]:
                return False, f"HTTP {resp.status_code}"
            return True, ""
        except Exception as e:
            # Considéré comme inaccessible uniquement en cas d'erreur de résolution
            if "Connection" in str(e) or "NameResolution" in str(e):
                return False, str(e)
            return True, ""

    def _record_inconsistency(
        self, title: str, url: str, app_status: str, internet_status: str, details: str
    ) -> None:
        """Enregistre une incohérence avérée."""
        self.inconsistencies.append(
            {
                "title": title,
                "url": url,
                "app_status": app_status,
                "internet_status": internet_status,
                "details": details,
            }
        )

    # =========================================================================
    # Étape 4 : Installation séquentielle des mods installables (API)
    # =========================================================================
    def install_mods_sequentially(self) -> None:
        """Installe séquentiellement les mods installables via l'API REST."""
        print("\n[ÉTAPE 4] Installation séquentielle des mods installables...")
        assert self.api_client is not None

        if self.skip_install:
            print(" -> Option --skip-install spécifiée. Aucune installation effectuée.")
            return

        # Mémoriser les mods déjà installés dans le jeu avant la simulation
        try:
            initial_installed = self.call_api("get_installed_mods").get("mods", [])
            self.installed_mod_ids_before = {m["id"] for m in initial_installed if isinstance(m, dict) and "id" in m}
        except Exception:
            self.installed_mod_ids_before = set()

        # Recherche des mods LoversLab installables
        db = DatabaseManager.get_instance()
        candidate_mods: List[CatalogMod] = []
        mod_with_deps: Optional[CatalogMod] = None

        with db.get_session() as session:
            # 1. Recherche prioritaire d'au moins 1 mod possédant des dépendances/prérequis déclarés
            mods_with_reqs = (
                session.query(CatalogMod)
                .filter(
                    CatalogMod.source == "loverslab",
                    CatalogMod.page_url.isnot(None),
                    CatalogMod.patreon_status != "LOCKED",
                    (CatalogMod.requirements_text.isnot(None)) | (CatalogMod.requirements_mods_json != "[]"),
                )
                .order_by(CatalogMod.updated_date.desc().nullslast())
                .all()
            )

            # Recherche alternative sur les mots-clés typiques de dépendances (animations, translations, etc.)
            if not mods_with_reqs:
                mods_with_reqs = (
                    session.query(CatalogMod)
                    .filter(
                        CatalogMod.source == "loverslab",
                        CatalogMod.page_url.isnot(None),
                        CatalogMod.patreon_status != "LOCKED",
                        (CatalogMod.title.ilike("%animation%"))
                        | (CatalogMod.title.ilike("%wicked%"))
                        | (CatalogMod.title.ilike("%traducc%"))
                        | (CatalogMod.title.ilike("%translation%")),
                    )
                    .order_by(CatalogMod.updated_date.desc().nullslast())
                    .all()
                )

            if mods_with_reqs:
                mod_with_deps = mods_with_reqs[0]

            # 2. Priorité aux mods validés comme téléchargeables en direct lors de l'étape 3
            if self.verified_downloadable_mods:
                v_ids = [m["id"] for m in self.verified_downloadable_mods if m.get("id")]
                if v_ids:
                    mods_by_id = {
                        m.id: m
                        for m in session.query(CatalogMod)
                        .filter(CatalogMod.id.in_(v_ids))
                        .all()
                    }
                    for vid in v_ids:
                        if vid in mods_by_id:
                            candidate_mods.append(mods_by_id[vid])

            # 3. Si aucun (ex: étape 3 sautée ou audit court), chercher tous les mods LoversLab non-verrouillés
            if not candidate_mods:
                candidate_mods = (
                    session.query(CatalogMod)
                    .filter(
                        CatalogMod.source == "loverslab",
                        CatalogMod.page_url.isnot(None),
                        CatalogMod.patreon_status != "LOCKED",
                    )
                    .order_by(CatalogMod.updated_date.desc().nullslast())
                    .limit(30)
                    .all()
                )

        if not candidate_mods and not mod_with_deps:
            print(" -> Aucun mod LoversLab directement installable détecté.")
            return

        # Assembler target_mods en plaçant le mod avec dépendances en tête de liste
        target_mods: List[CatalogMod] = []
        if mod_with_deps:
            target_mods.append(mod_with_deps)
            print(f" -> Mod avec dépendances inclus prioritairement : '{mod_with_deps.title}'")

        for m in candidate_mods:
            if not any(tm.id == m.id for tm in target_mods):
                target_mods.append(m)

        if self.max_installs is not None and self.max_installs > 0:
            target_mods = target_mods[: self.max_installs]

        print(f" -> {len(target_mods)} mod(s) sélectionné(s) pour installation séquentielle.")

        for idx, mod in enumerate(target_mods, start=1):
            print(f"\n[{idx}/{len(target_mods)}] Installation de : '{mod.title}' (ID #{mod.remote_id})...")
            start_t = time.time()
            self.stats["installations_attempted"] += 1

            try:
                res = self.call_api(
                    "install_mod",
                    catalog_mod_id=mod.id,
                    source=mod.source,
                    remote_id=mod.remote_id,
                    page_url=mod.page_url,
                    title=mod.title,
                )
                duration = time.time() - start_t
                success = res.get("success", False)
                msg = res.get("message", "")
                installed_deps = res.get("installed_dependencies", [])

                if success:
                    print(f" -> [OK] Succès en {duration:.1f}s : {msg}")
                    self.stats["installations_succeeded"] += 1
                else:
                    print(f" -> [FAIL] Échec en {duration:.1f}s : {msg}")
                    self.stats["installations_failed"] += 1

                self.installation_results.append(
                    {
                        "title": mod.title,
                        "source": mod.source,
                        "remote_id": mod.remote_id,
                        "duration_sec": round(duration, 1),
                        "success": success,
                        "message": msg,
                        "installed_dependencies": installed_deps,
                    }
                )
            except Exception as e:
                duration = time.time() - start_t
                print(f" -> [FAIL] Exception lors de l'installation : {e}")
                self.stats["installations_failed"] += 1
                self.installation_results.append(
                    {
                        "title": mod.title,
                        "source": mod.source,
                        "remote_id": mod.remote_id,
                        "duration_sec": round(duration, 1),
                        "success": False,
                        "message": f"Exception API: {e}",
                        "installed_dependencies": [],
                    }
                )

    def cleanup_installed_test_mods(self) -> None:
        """Désinstalle séquentiellement les mods de test installés pendant la simulation."""
        print("\n[ÉTAPE 4.5] Nettoyage post-test des mods installés...")
        if self.keep_installed:
            print(" -> Option --keep-installed spécifiée. Les mods restent installés dans le jeu.")
            return

        try:
            curr_installed = self.call_api("get_installed_mods").get("mods", [])
        except Exception as e:
            print(f" [WARNING] Impossible de récupérer la liste des mods installés via l'API : {e}")
            return

        newly_installed = [m for m in curr_installed if m.get("id") not in self.installed_mod_ids_before]
        if not newly_installed:
            print(" -> Aucun nouveau mod installé à nettoyer.")
            return

        print(f" -> {len(newly_installed)} mod(s) de test détecté(s) pour désinstallation automatique.")
        for im in newly_installed:
            mod_id = im["id"]
            title = im.get("title", "Mod")
            folder_name = im.get("folder_name", "")
            try:
                res = self.call_api("uninstall_mod", mod_id)
                success = res.get("success", False)
                msg = res.get("message", "")
                if success:
                    print(f" -> [OK] Nettoyé : '{title}' ({folder_name})")
                    self.stats["cleaned_mods_count"] += 1
                else:
                    print(f" -> [FAIL] Échec nettoyage : '{title}' : {msg}")
                self.cleanup_results.append({
                    "title": title,
                    "folder": folder_name,
                    "success": success,
                    "message": msg,
                })
            except Exception as e:
                print(f" -> [FAIL] Exception nettoyage '{title}' : {e}")
                self.cleanup_results.append({
                    "title": title,
                    "folder": folder_name,
                    "success": False,
                    "message": str(e),
                })

    # =========================================================================
    # Étape 5 : Récupération séquentielle des logs & génération du rapport final
    # =========================================================================
    def collect_errors_and_generate_report(self) -> Path:
        """Parcourt tous les logs, filtre les messages d'information et génère le rapport Markdown."""
        print("\n[ÉTAPE 5] Récupération séquentielle des logs et génération du rapport final...")
        self.stats["end_time"] = datetime.now()

        # 1. Collecte séquentielle des logs depuis le démarrage du test
        all_raw_lines: List[str] = []

        # Lecture depuis app.log sur le disque (à partir de l'offset initial)
        log_file = AppConfig.get_logs_dir() / "app.log"
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    if self.initial_log_offset > 0:
                        f.seek(self.initial_log_offset)
                    all_raw_lines.extend(f.readlines())
            except Exception as e:
                print(f" [WARNING] Erreur lors de la lecture de app.log : {e}")

        # Complément via l'API pour les derniers logs en mémoire vive
        try:
            logs_resp = self.call_api("get_logs", limit=2000)
            api_items = logs_resp.get("items", [])
            existing_set = set(line.strip() for line in all_raw_lines[-500:])
            for item in api_items:
                if item.strip() not in existing_set:
                    all_raw_lines.append(item.rstrip("\n") + "\n")
        except Exception as e:
            print(f" [WARNING] Impossible de récupérer les logs via l'API : {e}")

        # 2. Filtrage strict : Éliminer [INFO] et [DEBUG], ne garder que [ERROR], [CRITICAL] et exceptions
        # ET exclure les logs antérieurs au lancement de cette simulation
        filtered_errors: List[str] = []
        is_capturing_traceback = False
        start_time_threshold = self.stats["start_time"].strftime("%Y-%m-%d %H:%M:%S")

        for raw_line in all_raw_lines:
            line = raw_line.strip()
            if not line:
                continue

            # Élimination stricte des niveaux INFO et DEBUG
            if "[INFO]" in line or "[DEBUG]" in line:
                is_capturing_traceback = False
                continue

            # Vérification horodatage si présent [YYYY-MM-DD HH:MM:SS]
            ts_match = re.match(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", line)
            if ts_match:
                line_ts = ts_match.group(1)
                if line_ts < start_time_threshold:
                    is_capturing_traceback = False
                    continue

            # Détection d'erreurs ou niveaux critiques
            if "[ERROR]" in line or "[CRITICAL]" in line or "Traceback (most recent call last):" in line:
                filtered_errors.append(line)
                if "Traceback (most recent call last):" in line:
                    is_capturing_traceback = True
                continue

            # Si on capture une trace de pile (traceback Python sans préfixe de log)
            if is_capturing_traceback:
                if line.startswith('File "') or line.startswith("  ") or re.search(r"^\w+Error:", line):
                    filtered_errors.append(line)
                else:
                    is_capturing_traceback = False

        self.filtered_errors = filtered_errors
        self.stats["errors_logged_count"] = len(filtered_errors)
        print(f" -> Logs filtrés : {len(filtered_errors)} message(s) d'erreur retenu(s) (INFO/DEBUG exclus).")

        # 3. Génération du rapport Markdown horodaté
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"simulation_rapport_{now_str}.md"

        start_time = self.stats["start_time"].strftime("%Y-%m-%d %H:%M:%S")
        end_time = self.stats["end_time"].strftime("%Y-%m-%d %H:%M:%S")

        with open(report_path, "w", encoding="utf-8") as rf:
            rf.write("# Rapport d'Exécution : Simulation Utilisateur & Audit de Cohérence\n\n")
            rf.write(f"- **Date d'exécution** : {start_time} à {end_time}\n")
            rf.write(f"- **URL de l'API ciblée** : `{self.api_url}`\n")
            rf.write(f"- **Paramètres** : `--max-pages {self.max_pages}`, `--max-installs {self.max_installs}`\n\n")

            # Synthèse chiffrée
            rf.write("## 1. Synthèse globale\n\n")
            rf.write("| Métrique | Valeur |\n")
            rf.write("| :--- | :--- |\n")
            rf.write(f"| Mods répertoriés dans le catalogue | **{self.stats['total_catalog_mods']}** |\n")
            rf.write(f"| Mods audités en direct sur Internet | **{self.stats['total_audited_mods']}** |\n")
            rf.write(f"| Incohérences détectées | **{self.stats['inconsistencies_count']}** |\n")
            rf.write(f"| Installations tentées | **{self.stats['installations_attempted']}** |\n")
            rf.write(f"| Installations réussies | **{self.stats['installations_succeeded']}** |\n")
            rf.write(f"| Installations échouées | **{self.stats['installations_failed']}** |\n")
            rf.write(f"| Mods de test désinstallés (nettoyés) | **{self.stats['cleaned_mods_count']}** |\n")
            rf.write(f"| Erreurs d'application relevées dans les logs | **{self.stats['errors_logged_count']}** |\n\n")

            # Tableau des incohérences
            rf.write("## 2. Incohérences détectées sur Internet\n\n")
            if not self.inconsistencies:
                rf.write("> [!NOTE]\n> Aucune incohérence détectée ! Tous les statuts en ligne correspondent.\n\n")
            else:
                rf.write(
                    "> [!WARNING]\n"
                    f"> {len(self.inconsistencies)} incohérence(s) relevée(s) entre les données locales et Internet :\n\n"
                )
                rf.write("| Titre du Mod | URL | Statut Application | Résultat Internet Réel | Explication |\n")
                rf.write("| :--- | :--- | :--- | :--- | :--- |\n")
                for inc in self.inconsistencies:
                    safe_title = inc["title"].replace("|", "-")
                    safe_url = inc["url"]
                    safe_app = inc["app_status"].replace("|", "-")
                    safe_net = inc["internet_status"].replace("|", "-")
                    safe_det = inc["details"].replace("|", "-")
                    rf.write(f"| {safe_title} | [{safe_title}]({safe_url}) | {safe_app} | {safe_net} | {safe_det} |\n")
                rf.write("\n")

            # Tableau des installations
            rf.write("## 3. Résultats des installations séquentielles\n\n")
            if not self.installation_results:
                rf.write("> Aucune installation n'a été exécutée (`--skip-install` ou aucun mod installable).\n\n")
            else:
                rf.write("| Mod | Durée | Résultat | Message | Dépendances Installées |\n")
                rf.write("| :--- | :--- | :--- | :--- | :--- |\n")
                for inst in self.installation_results:
                    status_icon = "✅ Succès" if inst["success"] else "❌ Échec"
                    safe_title = inst["title"].replace("|", "-")
                    safe_msg = inst["message"].replace("|", "-")
                    deps_str = ", ".join(inst["installed_dependencies"]) if inst["installed_dependencies"] else "Aucune"
                    rf.write(
                        f"| {safe_title} | {inst['duration_sec']}s | {status_icon} | {safe_msg} | {deps_str} |\n"
                    )
                rf.write("\n")

            if self.cleanup_results:
                rf.write("### 3.1 Nettoyage post-test des mods\n\n")
                rf.write("| Mod | Dossier | Résultat | Message |\n")
                rf.write("| :--- | :--- | :--- | :--- |\n")
                for cl in self.cleanup_results:
                    st = "✅ Succès" if cl["success"] else "❌ Échec"
                    rf.write(f"| {cl['title'].replace('|', '-')} | `{cl['folder']}` | {st} | {cl['message'].replace('|', '-')} |\n")
                rf.write("\n")

            # Section Erreurs d'application relevées
            rf.write("## 4. Erreurs d'application relevées (Filtre strict : sans INFO/DEBUG)\n\n")
            if not self.filtered_errors:
                rf.write("> Aucune erreur `[ERROR]` ou `[CRITICAL]` enregistrée pendant la session.\n\n")
            else:
                rf.write("```text\n")
                for err in self.filtered_errors:
                    rf.write(f"{err}\n")
                rf.write("```\n")

        print("\n================================================================================")
        print(" RAPPORT GÉNÉRÉ AVEC SUCCÈS")
        print(f" Chemin absolu : {report_path.resolve()}")
        print("================================================================================\n")

        return report_path.resolve()

    def run(self) -> None:
        """Exécute toutes les étapes de la simulation."""
        print("=" * 80)
        print(" DÉMARRAGE DE LA SIMULATION UTILISATEUR & AUDIT (SIMS 4 MODS MANAGER)")
        print("=" * 80)

        try:
            self.ensure_api_server()
            self.setup_loverslab_session()
            self.sync_catalog()
            self.audit_mods_consistency()
            self.install_mods_sequentially()
            self.cleanup_installed_test_mods()
        finally:
            self.collect_errors_and_generate_report()


def main():
    parser = argparse.ArgumentParser(
        description="Script de simulation des actions utilisateur via l'API REST et audit de cohérence Internet."
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="URL de l'API REST (défaut : http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Nombre de pages LoversLab à scraper par catégorie (0 pour toutes les pages, défaut : 1)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Scraper l'intégralité du site LoversLab (équivalent à --max-pages 0)",
    )
    parser.add_argument(
        "--max-installs",
        type=int,
        default=None,
        help="Nombre maximal de mods installables à installer séquentiellement (défaut : tous)",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="N'exécuter que l'audit et le scraping sans installer de mod dans le jeu",
    )
    parser.add_argument(
        "--force-login",
        action="store_true",
        help="Forcer l'ouverture du navigateur Playwright pour réauthentifier LoversLab",
    )
    parser.add_argument(
        "--keep-installed",
        action="store_true",
        help="Conserver les mods installés dans le jeu sans les désinstaller automatiquement à la fin de la simulation",
    )

    args = parser.parse_args()

    max_pages = 0 if args.full else args.max_pages

    runner = SimulationRunner(
        api_url=args.api_url,
        max_pages=max_pages,
        max_installs=args.max_installs,
        skip_install=args.skip_install,
        force_login=args.force_login,
    )
    runner.run()


if __name__ == "__main__":
    main()
