from typing import List, Dict, Any, Optional
from src.providers import ProviderRegistry
from src.core.session_manager import SessionManager
from src.utils.logger import logger


class RequirementReporterService:
    """
    Centralized service for generating standardized English messages and managing
    forum interpellation for unidentified mod requirements across all providers.
    Directly queries the provider for live duplicate prevention (zero local DB storage).
    """

    @staticmethod
    def format_author_mention(author: str) -> str:
        """Sanitizes and formats the author handle with '@'."""
        clean = (author or "Author").strip()
        if not clean:
            return "@Author"
        if not clean.startswith("@"):
            return f"@{clean}"
        return clean

    @classmethod
    def build_english_message(
        cls,
        mod_title: str,
        author: str,
        missing_modules: Optional[List[str]] = None,
        unnecessary_modules: Optional[List[str]] = None,
    ) -> str:
        """
        Builds a standardized, polite English message mentioning the author
        and grouping both unidentified requirement modules and unnecessary requirement items.
        """
        mention = cls.format_author_mention(author)
        title_str = mod_title.strip() if mod_title else "this mod"

        clean_missing = [m.strip() for m in (missing_modules or []) if m and m.strip()]
        clean_unnecessary = [m.strip() for m in (unnecessary_modules or []) if m and m.strip()]

        if not clean_missing and not clean_unnecessary:
            return f"Hi {mention},\n\nCould you please review the Requirements section for \"{title_str}\"?\n\nThank you!"

        sections = []

        if clean_missing:
            items_str = "\n".join(f"- {m}" for m in clean_missing)
            if clean_unnecessary:
                sections.append(
                    f"1) The following required module(s) could not be identified or found in the catalog:\n"
                    f"{items_str}\n"
                    f"Could you please check or clarify the exact name or link for these requirements "
                    f"so that players and mod managers can locate and install them properly?"
                )
            else:
                sections.append(
                    f"In the Requirements section for \"{title_str}\", the following module(s) "
                    f"could not be identified or found in the catalog:\n"
                    f"{items_str}\n\n"
                    f"Could you please check or clarify the exact name or link for these requirements "
                    f"so that players and mod managers can locate and install them properly?"
                )

        if clean_unnecessary:
            items_str = "\n".join(f"- {m}" for m in clean_unnecessary)
            if clean_missing:
                sections.append(
                    f"2) Additionally, the following item(s) listed under Requirements do not appear to be mods or required files (they appear to be comments or notes):\n"
                    f"{items_str}\n"
                    f"Could you please remove these comments from the Requirements section to ensure a coherent dependency list and avoid false detection results for players and mod managers?"
                )
            else:
                sections.append(
                    f"In the Requirements section for \"{title_str}\", the following item(s) are listed "
                    f"but do not appear to be mods or required files (they appear to be comments or text notes):\n"
                    f"{items_str}\n\n"
                    f"Could you please remove these comments from the Requirements section "
                    f"to maintain a coherent dependency list and avoid false detection results in mod managers?"
                )

        body = "\n\n".join(sections)
        return f"Hi {mention},\n\n{body}\n\nThank you!"

    @classmethod
    def check_report_status(
        cls,
        source: str,
        page_url: str,
        mod_title: str,
        author: str,
        missing_modules: Optional[List[str]] = None,
        unnecessary_modules: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Checks live on the provider's site whether the user has already posted
        an interpellation for this mod and these requirements.
        """
        clean_author = cls.format_author_mention(author)
        missing_mods = missing_modules or []
        unnecessary_mods = unnecessary_modules or []
        formatted_message = cls.build_english_message(mod_title, author, missing_mods, unnecessary_mods)

        # 1. Check member authentication
        if not SessionManager.is_member_authenticated(source):
            return {
                "can_report": False,
                "already_reported": False,
                "reported_at": None,
                "formatted_message": formatted_message,
                "author": clean_author,
                "is_authenticated": False,
                "reason": "Compte membre non connecté pour cette source.",
            }

        provider = ProviderRegistry.get_provider(source)
        if not provider:
            return {
                "can_report": False,
                "already_reported": False,
                "reported_at": None,
                "formatted_message": formatted_message,
                "author": clean_author,
                "is_authenticated": True,
                "reason": f"Fournisseur inconnu: '{source}'.",
            }

        # 2. Live remote check on provider forum
        all_keywords = missing_mods + unnecessary_mods
        try:
            already_posted, posted_date = provider.check_user_already_commented(
                page_url=page_url, required_keywords=all_keywords
            )
        except Exception as e:
            logger.error(f"Erreur lors de la vérification en direct sur {source}: {e}")
            already_posted, posted_date = False, None

        if already_posted:
            return {
                "can_report": False,
                "already_reported": True,
                "reported_at": posted_date or "précédemment",
                "formatted_message": formatted_message,
                "author": clean_author,
                "is_authenticated": True,
                "reason": f"Message déjà posté sur le forum le {posted_date or 'précédemment'}.",
            }

        return {
            "can_report": True,
            "already_reported": False,
            "reported_at": None,
            "formatted_message": formatted_message,
            "author": clean_author,
            "is_authenticated": True,
            "reason": None,
        }

    @classmethod
    def submit_report(
        cls,
        source: str,
        page_url: str,
        mod_title: str,
        author: str,
        missing_modules: Optional[List[str]] = None,
        unnecessary_modules: Optional[List[str]] = None,
        custom_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validates anti-duplicate check live on the provider forum, then posts the message.
        """
        status = cls.check_report_status(
            source=source,
            page_url=page_url,
            mod_title=mod_title,
            author=author,
            missing_modules=missing_modules,
            unnecessary_modules=unnecessary_modules,
        )

        if not status["is_authenticated"]:
            return {
                "success": False,
                "message": "Veuillez vous connecter avec votre compte membre dans l'onglet 'Comptes' pour pouvoir poster.",
                "already_reported": False,
                "reported_at": None,
            }

        if status["already_reported"]:
            date_info = status["reported_at"] or "précédemment"
            return {
                "success": False,
                "message": f"L'auteur a déjà été interpelé pour ce mod le {date_info}. Aucun nouveau message n'a été envoyé.",
                "already_reported": True,
                "reported_at": status["reported_at"],
            }

        provider = ProviderRegistry.get_provider(source)
        if not provider:
            return {
                "success": False,
                "message": f"Fournisseur non trouvé: {source}",
                "already_reported": False,
                "reported_at": None,
            }

        message_to_send = custom_message or status["formatted_message"]
        success, result_msg = provider.post_mod_comment(page_url, message_to_send)

        if success:
            logger.info(f"Rapport de dépendances manquantes envoyé pour {mod_title} sur {source}.")
            return {
                "success": True,
                "message": result_msg,
                "already_reported": True,
                "reported_at": "à l'instant",
            }
        else:
            return {
                "success": False,
                "message": result_msg,
                "already_reported": False,
                "reported_at": None,
            }
