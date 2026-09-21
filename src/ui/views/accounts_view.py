"""
AccountsView: Manages site sessions, interactive Cloudflare solving, tests and resets via API.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QMessageBox,
)
from PySide6.QtCore import Signal

from src.api.client import get_api_client
from src.ui.components.progress_dialog import ProgressDialog
from src.ui.components.account_card import AccountCardWidget, LoginWorker
from src.i18n import tr
from src.utils.logger import logger

__all__ = ["AccountsView", "LoginWorker"]


class AccountsView(QWidget):
    """View to manage site sessions, interactive Cloudflare solving, tests and resets via API."""

    login_successful = Signal(str)  # provider_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.card_widgets = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Title
        self.title_lbl = QLabel(tr("accounts.title"))
        self.title_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(self.title_lbl)

        self.subtitle_lbl = QLabel(tr("accounts.subtitle"))
        self.subtitle_lbl.setWordWrap(True)
        self.subtitle_lbl.setStyleSheet("font-size: 13px; color: #94a3b8;")
        layout.addWidget(self.subtitle_lbl)

        # Providers Cards
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(16)

        # 1. LoversLab Card
        self.loverslab_card = AccountCardWidget(
            provider_name="loverslab",
            title_key="accounts.loverslab_title",
            desc_key="accounts.loverslab_desc",
            parent=self,
        )
        self.loverslab_card.clear_requested.connect(self._on_clear_clicked)
        self.loverslab_card.test_requested.connect(self._on_test_clicked)
        self.loverslab_card.login_requested.connect(self.open_login_window)
        self.cards_layout.addWidget(self.loverslab_card)

        # 2. Patreon Card
        self.patreon_card = AccountCardWidget(
            provider_name="patreon",
            title_key="accounts.patreon_title",
            desc_key="accounts.patreon_desc",
            parent=self,
        )
        self.patreon_card.clear_requested.connect(self._on_clear_clicked)
        self.patreon_card.test_requested.connect(self._on_test_clicked)
        self.patreon_card.login_requested.connect(self.open_login_window)
        self.cards_layout.addWidget(self.patreon_card)

        layout.addLayout(self.cards_layout)
        layout.addStretch()

        # Backward compatibility dictionary for card_widgets
        for card in [self.loverslab_card, self.patreon_card]:
            self.card_widgets[card.provider_name] = {
                "title_lbl": card.title_lbl,
                "title_key": card.title_key,
                "desc_lbl": card.desc_lbl,
                "desc_key": card.desc_key,
                "clear_btn": card.clear_btn,
                "test_btn": card.test_btn,
                "login_btn": card.login_btn,
            }

        self.refresh_statuses()

    def retranslate_ui(self):
        """Retranslates all text in AccountsView dynamically."""
        self.title_lbl.setText(tr("accounts.title"))
        self.subtitle_lbl.setText(tr("accounts.subtitle"))
        self.loverslab_card.retranslate_ui()
        self.patreon_card.retranslate_ui()
        self.refresh_statuses()

    def refresh_statuses(self):
        """Loads account statuses through API /api/accounts."""
        try:
            client = get_api_client()
            accounts = client.get_accounts()
            for acc in accounts:
                p_name = acc.get("provider_name")
                is_member = acc.get("is_member", False)
                is_ready = acc.get("is_ready", False)
                display = acc.get("user_display_name", "")

                card = (
                    self.loverslab_card
                    if p_name == "loverslab"
                    else (self.patreon_card if p_name == "patreon" else None)
                )
                if card:
                    card.update_badge(is_member, is_ready, display)
        except Exception as e:
            logger.error(f"Erreur API lors du rafraîchissement des comptes: {e}")

    def _on_clear_clicked(self, provider_name: str):
        reply = QMessageBox.question(
            self,
            tr("accounts.clear_confirm_title"),
            tr("accounts.clear_confirm_msg", provider=provider_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                client = get_api_client()
                res = client.clear_account(provider_name)
                self.refresh_statuses()
                QMessageBox.information(
                    self, tr("accounts.clear_success_title"), res.get("message", tr("accounts.clear_success_msg"))
                )
            except Exception as e:
                QMessageBox.warning(self, tr("dialogs.error_title"), f"{e}")

    def _on_test_clicked(self, provider_name: str):
        try:
            client = get_api_client()
            res = client.test_account(provider_name)
            ok = res.get("success", False)
            msg = res.get("message", "")
            if ok:
                QMessageBox.information(self, tr("accounts.test_success_title"), f"{msg}")
                # Auto-trigger background sync if not already running
                try:
                    sync_st = client.get_catalog_sync_status()
                    if not sync_st.get("is_running", False):
                        client.start_catalog_sync(max_pages=0)
                        logger.info(
                            f"Synchronisation automatique du catalogue lancée suite au test validé de {provider_name}."
                        )
                except Exception as e:
                    logger.debug(f"Impossible de démarrer la synchro auto après test: {e}")
            else:
                QMessageBox.warning(self, tr("accounts.test_failed_title"), f"{msg}")
        except Exception as e:
            QMessageBox.warning(self, tr("dialogs.error_title"), f"{e}")
        self.refresh_statuses()

    def open_login_window(self, provider_name: str):
        from src.ui.components.browser_download_dialog import BrowserDownloadDialog

        if not BrowserDownloadDialog.ensure_browser_ready(parent=self):
            return

        self.progress_dlg = ProgressDialog(tr("accounts.login_dlg_title", provider=provider_name), self)
        self.progress_dlg.set_status(tr("accounts.login_dlg_status", provider=provider_name))
        self.progress_dlg.set_details(tr("accounts.login_dlg_details"))
        self.progress_dlg.set_indeterminate(True)
        self.progress_dlg.show()

        self.worker = LoginWorker(provider_name)
        self.worker.finished.connect(self._on_login_finished)
        self.worker.start()

    def _on_login_finished(self, success: bool, msg: str):
        if hasattr(self, "progress_dlg"):
            self.progress_dlg.close()
        provider = getattr(self, "worker", None)
        p_name = provider.provider_name if provider else "compte"

        self.refresh_statuses()

        if success:
            try:
                client = get_api_client()
                client.start_catalog_sync(max_pages=0)
                logger.info(
                    f"Synchronisation automatique intégrale du catalogue lancée suite à l'authentification de {p_name}."
                )
            except Exception as e:
                logger.error(f"Impossible de lancer la synchronisation automatique: {e}")

            QMessageBox.information(self, tr("accounts.login_success_title"), tr("accounts.login_success_msg", msg=msg))
            self.login_successful.emit(p_name)
        else:
            QMessageBox.warning(self, tr("dialogs.info_title"), msg)
