import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Callable
from bs4 import BeautifulSoup

from src.core.session_manager import SessionManager
from src.utils.logger import logger
from src.utils.network import stream_download, is_external_hosted


def extract_download_candidates(soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
    """
    Extracts and prioritizes download candidate files from an IPS download selection page.
    Prioritizes direct archives (.zip, .package, .rar, .7z) with explicit file sizes over external/redirect links.
    """
    candidates = []
    rows = soup.select(".ipsDataItem, li[data-rowid]")
    for row in rows:
        btn = row.select_one("a[href*='do=download'], a[data-action='download']")
        if not btn or not btn.get("href"):
            continue
        href = btn["href"]
        if not href.startswith("http"):
            href = base_url + href

        title_el = row.select_one(".ipsDataItem_title, [data-role='filename'], h4, strong")
        title = title_el.get_text(strip=True) if title_el else ""

        meta_el = row.select_one(".ipsType_light, .ipsDataItem_meta")
        meta = meta_el.get_text(strip=True) if meta_el else ""

        score = 0
        if re.search(r"\.(?:zip|rar|7z|package|ts4script)\b", title, re.IGNORECASE):
            score += 100
        elif re.search(r"\b(?:zip|rar|7z|package)\b", title, re.IGNORECASE):
            score += 50

        if re.search(r"\d+(?:\.\d+)?\s*(?:MB|GB|KB|Mo|Go|Ko)\b", meta, re.IGNORECASE):
            score += 50

        candidates.append({"url": href, "title": title, "meta": meta, "score": score})

    if not candidates:
        generic = soup.select(
            "a[href*='do=download'][href*='confirm='], a[href*='do=download&r='], a.ipsButton_primary[href*='do=download'], a[data-action='download']"
        )
        for g in generic:
            href = g.get("href", "")
            if href and not href.startswith("#"):
                if not href.startswith("http"):
                    href = base_url + href
                candidates.append({"url": href, "title": g.get_text(strip=True), "meta": "", "score": 0})

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


def download_loverslab_file(
    download_url: str,
    dest_path: Path,
    patreon_provider,
    base_url: str = "https://www.loverslab.com",
    progress_callback: Optional[Callable[[int, str, str], None]] = None,
) -> Tuple[bool, str]:
    """
    Downloads a direct file from LoversLab resolving multi-step IPS confirmation pages.
    """
    if "patreon.com" in download_url:
        return patreon_provider.download_mod_file(download_url, dest_path, progress_callback=progress_callback)

    session = SessionManager.get_http_session("loverslab")
    is_member = SessionManager.is_member_authenticated("loverslab")

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Lancement du téléchargement LoversLab: {download_url} (Compte membre={is_member})")
        if progress_callback:
            progress_callback(
                5, "Connexion aux serveurs LoversLab...", "Résolution de la page de téléchargement..."
            )

        resp = session.get(download_url, timeout=45, allow_redirects=False)
        logger.info(
            f"Réponse initiale LoversLab -> Code HTTP {resp.status_code}, Type: {resp.headers.get('Content-Type', '')}"
        )

        if resp.status_code in [301, 302, 303, 307, 308]:
            target = resp.headers.get("Location", "")
            logger.info(f"Redirection détectée lors du téléchargement: {target}")
            if "patreon.com" in target.lower():
                return patreon_provider.download_mod_file(
                    target, dest_path, progress_callback=progress_callback
                )

            matched_host = is_external_hosted(target)
            if matched_host:
                msg = f"Ce contenu est hébergé sur un service externe ({matched_host}). Veuillez l'ouvrir dans votre navigateur pour le télécharger."
                logger.warning(msg)
                return False, msg

            resp = session.get(target, timeout=45, allow_redirects=True)

        logger.info(
            f"Réponse LoversLab -> Code HTTP {resp.status_code}, Type: {resp.headers.get('Content-Type', '')}"
        )

        final_url = str(getattr(resp, "url", ""))
        matched_host = is_external_hosted(final_url)
        if matched_host:
            msg = f"Ce contenu est hébergé sur un service externe ({matched_host}). Veuillez l'ouvrir dans votre navigateur pour le télécharger."
            logger.warning(msg)
            return False, msg

        if resp.status_code == 403:
            msg = "Accès refusé par LoversLab (Code 403). Le téléchargement exige un compte membre connecté. Veuillez vous connecter dans l'onglet 'Comptes & Anti-Bot'."
            logger.error(msg)
            return False, msg
        elif resp.status_code in [504, 502]:
            msg = f"Délai d'attente dépassé sur le serveur LoversLab (Code {resp.status_code}). Veuillez réessayer dans quelques instants."
            logger.error(msg)
            return False, msg
        elif resp.status_code != 200:
            return False, f"Code d'erreur HTTP {resp.status_code}"

        content_type = resp.headers.get("Content-Type", "").lower()
        content_disp = resp.headers.get("Content-Disposition", "").lower()

        if "html" not in content_type or "attachment" in content_disp or "filename=" in content_disp:
            return stream_download(resp, dest_path, progress_callback, "Téléchargement Direct")

        soup = BeautifulSoup(resp.text, "html.parser")

        if "data-focus-guest" in resp.text and ("Sign In" in resp.text or "Existing user" in resp.text):
            msg = "LoversLab exige d'être connecté avec un compte membre pour télécharger. Veuillez vous connecter dans l'onglet 'Comptes & Anti-Bot'."
            logger.error(msg)
            return False, msg

        candidates = extract_download_candidates(soup, base_url)
        last_err = "Impossible de résoudre le bouton de téléchargement final sur la page LoversLab."
        headers = {"Referer": download_url}

        for cand in candidates:
            cand_url = cand["url"]
            cand_title = cand.get("title", "")
            logger.info(f"Évaluation du candidat de téléchargement : '{cand_title}' ({cand_url})")
            if progress_callback:
                progress_callback(10, "Lien direct résolu", f"Téléchargement : {cand_title or 'archive'}")

            try:
                bin_resp = session.get(cand_url, headers=headers, stream=True, timeout=90, allow_redirects=False)

                if bin_resp.status_code in [301, 302, 303, 307, 308]:
                    loc = bin_resp.headers.get("Location", "")
                    logger.info(f"Candidat '{cand_title}' redirige vers: {loc}")
                    if "patreon.com" in loc.lower():
                        return patreon_provider.download_mod_file(
                            loc, dest_path, progress_callback=progress_callback
                        )

                    ext_host = is_external_hosted(loc)
                    if ext_host:
                        logger.info(
                            f"Candidat '{cand_title}' est hébergé en externe ({ext_host}). Vérification d'autres fichiers directs..."
                        )
                        last_err = f"Le contenu est hébergé sur un service externe ({ext_host})."
                        continue

                    bin_resp = session.get(loc, headers=headers, stream=True, timeout=90, allow_redirects=True)

                if bin_resp.status_code == 200:
                    content_type = bin_resp.headers.get("Content-Type", "").lower()
                    content_disp = bin_resp.headers.get("Content-Disposition", "").lower()
                    if "html" not in content_type or "attachment" in content_disp or "filename=" in content_disp:
                        return stream_download(
                            bin_resp, dest_path, progress_callback, f"Téléchargement {cand_title or 'LoversLab'}"
                        )
                    else:
                        logger.debug(f"Candidat '{cand_title}' a renvoyé du HTML au lieu d'un binaire.")
                else:
                    logger.warning(f"Candidat '{cand_title}' a retourné le code HTTP {bin_resp.status_code}.")
                    last_err = f"Échec du téléchargement final (Code HTTP {bin_resp.status_code})"
            except Exception as c_err:
                logger.warning(f"Erreur lors du test du candidat '{cand_title}': {c_err}")
                last_err = str(c_err)

        attach_link = soup.select_one("a[href*='applications/core/interface/file/attachment.php']")
        if attach_link and attach_link.get("href"):
            att_href = attach_link["href"]
            if not att_href.startswith("http"):
                att_href = base_url + att_href
            logger.info(f"Lien de pièce jointe IPS direct trouvé : {att_href}")
            if progress_callback:
                progress_callback(10, "Pièce jointe trouvée", "Démarrage du téléchargement...")
            bin_resp = session.get(att_href, headers=headers, stream=True, timeout=90, allow_redirects=True)
            if bin_resp.status_code == 200:
                return stream_download(bin_resp, dest_path, progress_callback, "Téléchargement LoversLab")
            else:
                return False, f"Échec du téléchargement final (Code HTTP {bin_resp.status_code})"

        return False, last_err

    except Exception as e:
        logger.error(f"Exception lors du téléchargement LoversLab ({download_url}): {e}", exc_info=True)
        return False, str(e)
