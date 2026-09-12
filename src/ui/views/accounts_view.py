from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QMessageBox,
)
from PySide6.QtCore import QThread, Signal

from src.api.client import get_api_client
from src.ui.components.progress_dialog import ProgressDialog
from src.i18n import tr
from src.utils.logger import logger


class LoginWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, provider_name: str):
        super().__init__()
        self.provider_name = provider_name

    def run(self):
        try:
            client = get_api_client()
            res = client.login_account(self.provider_name, timeout_seconds=300)
            self.finished.emit(res.get("success", False), res.get("message", ""))
        except Exception as e:
            self.finished.emit(False, f"Erreur lors de l'appel API login: {e}")


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
        self.loverslab_card = self._create_account_card(
            provider_name="loverslab",
            title_key="accounts.loverslab_title",
            desc_key="accounts.loverslab_desc",
        )
        self.cards_layout.addWidget(self.loverslab_card)

        # 2. Patreon Card
        self.patreon_card = self._create_account_card(
            provider_name="patreon",
            title_key="accounts.patreon_title",
            desc_key="accounts.patreon_desc",
        )
        self.cards_layout.addWidget(self.patreon_card)

        layout.addLayout(self.cards_layout)
        layout.addStretch()

        self.refresh_statuses()

    def _create_account_card(self, provider_name: str, title_key: str, desc_key: str) -> QFrame:
        card = QFrame()
        card.setObjectName(f"card_{provider_name}")
        card.setStyleSheet("""
            QFrame {
                background-color: #161824;
                border: 1px solid #282e44;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        # Header
        h_layout = QHBoxLayout()
        t_label = QLabel(tr(title_key))
        t_label.setStyleSheet("font-size: 15px; font-weight: 600; color: #f8fafc;")
        h_layout.addWidget(t_label)

        h_layout.addStretch()

        status_badge = QLabel(tr("accounts.status_unconfigured"))
        status_badge.setObjectName(f"status_{provider_name}")
        status_badge.setStyleSheet(
            "background-color: #334155; color: #94a3b8; border-radius: 10px; padding: 4px 14px; font-weight: 600; font-size: 12px;"
        )
        h_layout.addWidget(status_badge)

        c_layout.addLayout(h_layout)

        # Description
        d_label = QLabel(tr(desc_key))
        d_label.setWordWrap(True)
        d_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
        c_layout.addWidget(d_label)

        # Action Buttons Row
        b_layout = QHBoxLayout()
        b_layout.setSpacing(10)

        # Clear Button
        clear_btn = QPushButton(tr("accounts.btn_clear"))
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #26171a;
                color: #fca5a5;
                border: 1px solid #7f1d1d;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #3f171e; }
        """)
        clear_btn.clicked.connect(lambda _, pn=provider_name: self._on_clear_clicked(pn))
        b_layout.addWidget(clear_btn)

        # Test Button
        test_btn = QPushButton(tr("accounts.btn_test"))
        test_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2438;
                color: #93c5fd;
                border: 1px solid #2563eb;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #27314d; }
        """)
        test_btn.clicked.connect(lambda _, pn=provider_name: self._on_test_clicked(pn))
        b_layout.addWidget(test_btn)

        b_layout.addStretch()

        # Login Browser Button
        login_btn = QPushButton(tr("accounts.btn_login"))
        login_btn.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #6366f1; }
        """)
        login_btn.clicked.connect(lambda _, pn=provider_name: self.open_login_window(pn))
        b_layout.addWidget(login_btn)

        c_layout.addLayout(b_layout)

        self.card_widgets[provider_name] = {
            "title_lbl": t_label,
            "title_key": title_key,
            "desc_lbl": d_label,
            "desc_key": desc_key,
            "clear_btn": clear_btn,
            "test_btn": test_btn,
            "login_btn": login_btn,
        }

        return card

    def retranslate_ui(self):
        """Retranslates all text in AccountsView dynamically."""
        self.title_lbl.setText(tr("accounts.title"))
        self.subtitle_lbl.setText(tr("accounts.subtitle"))
        for info in self.card_widgets.values():
            info["title_lbl"].setText(tr(info["title_key"]))
            info["desc_lbl"].setText(tr(info["desc_key"]))
            info["clear_btn"].setText(tr("accounts.btn_clear"))
            info["test_btn"].setText(tr("accounts.btn_test"))
            info["login_btn"].setText(tr("accounts.btn_login"))
        self.refresh_statuses()

    def refresh_statuses(self):
        """Loads account statuses through API /api/accounts."""
        try:
            accounts = self.api_client.get_accounts()
            for acc in accounts:
                p_name = acc.get("provider_name")
                badge = self.findChild(QLabel, f"status_{p_name}")
                if not badge:
                    continue

                is_member = acc.get("is_member", False)
                is_ready = acc.get("is_ready", False)
                display = acc.get("user_display_name", "")

                if is_member:
                    badge.setText(tr("accounts.status_member", display=display or "Actif"))
                    badge.setStyleSheet(
                        "background-color: #064e3b; color: #34d399; border-radius: 10px; padding: 4px 14px; font-weight: 700;"
                    )
                elif is_ready:
                    badge.setText(tr("accounts.status_antibot_ok"))
                    badge.setStyleSheet(
                        "background-color: #451a03; color: #fbbf24; border-radius: 10px; padding: 4px 14px; font-weight: 700;"
                    )
                else:
                    badge.setText(tr("accounts.status_unconfigured"))
                    badge.setStyleSheet(
                        "background-color: #334155; color: #94a3b8; border-radius: 10px; padding: 4px 14px; font-weight: 600;"
                    )
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
                res = self.api_client.clear_account(provider_name)
                self.refresh_statuses()
                QMessageBox.information(
                    self, tr("accounts.clear_success_title"), res.get("message", tr("accounts.clear_success_msg"))
                )
            except Exception as e:
                QMessageBox.warning(self, tr("dialogs.error_title"), f"{e}")

    def _on_test_clicked(self, provider_name: str):
        try:
            res = self.api_client.test_account(provider_name)
            ok = res.get("success", False)
            msg = res.get("message", "")
            if ok:
                QMessageBox.information(self, tr("accounts.test_success_title"), f"{msg}")
                # Auto-trigger background sync if not already running
                try:
                    sync_st = self.api_client.get_catalog_sync_status()
                    if not sync_st.get("is_running", False):
                        self.api_client.start_catalog_sync(max_pages=0)
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
                self.api_client.start_catalog_sync(max_pages=0)
                logger.info(
                    f"Synchronisation automatique intégrale du catalogue lancée suite à l'authentification de {p_name}."
                )
            except Exception as e:
                logger.error(f"Impossible de lancer la synchronisation automatique: {e}")

            QMessageBox.information(
                self, tr("accounts.login_success_title"), tr("accounts.login_success_msg", msg=msg)
            )
            self.login_successful.emit(p_name)
        else:
            QMessageBox.warning(self, tr("dialogs.info_title"), msg)
