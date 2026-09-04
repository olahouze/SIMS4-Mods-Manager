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
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Title
        title = QLabel("Comptes, Sessions & Anti-Bot")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Connectez vos comptes pour contourner les protections anti-bot (Cloudflare, consentement adulte LoversLab) "
            "et vérifier vos accès abonnés sur Patreon."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 13px; color: #94a3b8;")
        layout.addWidget(subtitle)

        # Providers Cards
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(16)

        # 1. LoversLab Card
        self.loverslab_card = self._create_account_card(
            provider_name="loverslab",
            title="LoversLab (Forum IPS & Téléchargements The Sims 4)",
            description="Permet le passage automatique de Cloudflare, la validation de l'avertissement adulte (+18 ans) et l'accès aux téléchargements directs.",
        )
        self.cards_layout.addWidget(self.loverslab_card)

        # 2. Patreon Card
        self.patreon_card = self._create_account_card(
            provider_name="patreon",
            title="Patreon (Accès Créateurs & Niveaux d'Abonnement)",
            description="Permet d'identifier si votre compte Patreon a débloqué les mods réservés aux abonnés / accès anticipé et de télécharger les pièces jointes.",
        )
        self.cards_layout.addWidget(self.patreon_card)

        layout.addLayout(self.cards_layout)
        layout.addStretch()

        self.refresh_statuses()

    def _create_account_card(self, provider_name: str, title: str, description: str) -> QFrame:
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
        t_label = QLabel(title)
        t_label.setStyleSheet("font-size: 15px; font-weight: 600; color: #f8fafc;")
        h_layout.addWidget(t_label)

        h_layout.addStretch()

        status_badge = QLabel("Non configuré")
        status_badge.setObjectName(f"status_{provider_name}")
        status_badge.setStyleSheet(
            "background-color: #334155; color: #94a3b8; border-radius: 10px; padding: 4px 14px; font-weight: 600; font-size: 12px;"
        )
        h_layout.addWidget(status_badge)

        c_layout.addLayout(h_layout)

        # Description
        d_label = QLabel(description)
        d_label.setWordWrap(True)
        d_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
        c_layout.addWidget(d_label)

        # Action Buttons Row
        b_layout = QHBoxLayout()
        b_layout.setSpacing(10)

        # Clear Button
        clear_btn = QPushButton("🗑️ Réinitialiser")
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
        test_btn = QPushButton("🔄 Tester la session")
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
        login_btn = QPushButton("🔑 Ouvrir le Navigateur de Connexion")
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
        return card

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
                    badge.setText(f"✓ Membre Connecté ({display or 'Actif'})")
                    badge.setStyleSheet(
                        "background-color: #064e3b; color: #34d399; border-radius: 10px; padding: 4px 14px; font-weight: 700;"
                    )
                elif is_ready:
                    badge.setText("⚠️ Anti-Bot Validé (Connexion requise pour téléchargements)")
                    badge.setStyleSheet(
                        "background-color: #451a03; color: #fbbf24; border-radius: 10px; padding: 4px 14px; font-weight: 700;"
                    )
                else:
                    badge.setText("Non configuré")
                    badge.setStyleSheet(
                        "background-color: #334155; color: #94a3b8; border-radius: 10px; padding: 4px 14px; font-weight: 600;"
                    )
        except Exception as e:
            logger.error(f"Erreur API lors du rafraîchissement des comptes: {e}")

    def _on_clear_clicked(self, provider_name: str):
        reply = QMessageBox.question(
            self,
            "Réinitialiser la session",
            f"Voulez-vous vraiment supprimer les cookies et réinitialiser le profil pour {provider_name} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                res = self.api_client.clear_account(provider_name)
                self.refresh_statuses()
                QMessageBox.information(self, "Réinitialisé", res.get("message", "Session réinitialisée."))
            except Exception as e:
                QMessageBox.warning(self, "Erreur", f"Échec de la réinitialisation: {e}")

    def _on_test_clicked(self, provider_name: str):
        try:
            res = self.api_client.test_account(provider_name)
            ok = res.get("success", False)
            msg = res.get("message", "")
            if ok:
                QMessageBox.information(self, "Test de session réussi", f"Statut : {msg}")
            else:
                QMessageBox.warning(self, "Test de session échoué", f"Statut : {msg}")
        except Exception as e:
            QMessageBox.warning(self, "Erreur API", f"Impossible de contacter l'API: {e}")
        self.refresh_statuses()

    def open_login_window(self, provider_name: str):
        self.progress_dlg = ProgressDialog(f"Session {provider_name}", self)
        self.progress_dlg.set_status(f"Ouverture du navigateur pour {provider_name}...")
        self.progress_dlg.set_details(
            "Passez Cloudflare ou connectez-vous, puis fermez simplement la fenêtre du navigateur."
        )
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
            # Trigger background catalog synchronization immediately
            try:
                self.api_client.start_catalog_sync(max_pages=5)
                logger.info(
                    f"Synchronisation automatique du catalogue lancée suite à l'authentification réussie de {p_name}."
                )
            except Exception as e:
                logger.error(f"Impossible de lancer la synchronisation automatique: {e}")

            QMessageBox.information(
                self, "Session Enregistrée", f"{msg}\n\nLa synchronisation du catalogue a démarré en arrière-plan !"
            )
            self.login_successful.emit(p_name)
        else:
            QMessageBox.warning(self, "Information", msg)
