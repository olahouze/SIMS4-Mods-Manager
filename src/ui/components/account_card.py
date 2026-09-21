"""
AccountCardWidget: Reusable UI card for site provider authentication (LoversLab, Patreon).
Encapsulates status badges, descriptions, action buttons and signal routing.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Signal

from src.api.client import get_api_client
from src.i18n import tr
from src.utils.thread_utils import BaseWorker


class LoginWorker(BaseWorker):
    finished = Signal(bool, str)

    def __init__(self, provider_name: str):
        super().__init__()
        self.provider_name = provider_name

    def run(self):
        self._is_running = True
        try:
            if self._is_cancelled:
                return
            client = get_api_client()
            res = client.login_account(self.provider_name, timeout_seconds=300)
            if not self._is_cancelled:
                self.finished.emit(res.get("success", False), res.get("message", ""))
        except Exception as e:
            if not self._is_cancelled:
                self.finished.emit(False, f"Erreur lors de l'appel API login: {e}")
        finally:
            self._is_running = False


class AccountCardWidget(QFrame):
    """Reusable account status & action card."""

    clear_requested = Signal(str)
    test_requested = Signal(str)
    login_requested = Signal(str)

    def __init__(self, provider_name: str, title_key: str, desc_key: str, parent=None):
        super().__init__(parent)
        self.provider_name = provider_name
        self.title_key = title_key
        self.desc_key = desc_key
        self.setObjectName(f"card_{provider_name}")
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #161824;
                border: 1px solid #282e44;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        c_layout = QVBoxLayout(self)
        c_layout.setSpacing(12)

        # Header
        h_layout = QHBoxLayout()
        self.title_lbl = QLabel(tr(self.title_key))
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: 600; color: #f8fafc;")
        h_layout.addWidget(self.title_lbl)

        h_layout.addStretch()

        self.status_badge = QLabel(tr("accounts.status_unconfigured"))
        self.status_badge.setObjectName(f"status_{self.provider_name}")
        self.status_badge.setStyleSheet(
            "background-color: #334155; color: #94a3b8; border-radius: 10px; padding: 4px 14px; font-weight: 600; font-size: 12px;"
        )
        h_layout.addWidget(self.status_badge)
        c_layout.addLayout(h_layout)

        # Description
        self.desc_lbl = QLabel(tr(self.desc_key))
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        c_layout.addWidget(self.desc_lbl)

        # Action Buttons Row
        b_layout = QHBoxLayout()
        b_layout.setSpacing(10)

        # Clear Button
        self.clear_btn = QPushButton(tr("accounts.btn_clear"))
        self.clear_btn.setStyleSheet("""
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
        self.clear_btn.clicked.connect(lambda: self.clear_requested.emit(self.provider_name))
        b_layout.addWidget(self.clear_btn)

        # Test Button
        self.test_btn = QPushButton(tr("accounts.btn_test"))
        self.test_btn.setStyleSheet("""
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
        self.test_btn.clicked.connect(lambda: self.test_requested.emit(self.provider_name))
        b_layout.addWidget(self.test_btn)

        b_layout.addStretch()

        # Login Browser Button
        self.login_btn = QPushButton(tr("accounts.btn_login"))
        self.login_btn.setStyleSheet("""
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
        self.login_btn.clicked.connect(lambda: self.login_requested.emit(self.provider_name))
        b_layout.addWidget(self.login_btn)

        c_layout.addLayout(b_layout)

    def update_badge(self, is_member: bool, is_ready: bool, display: Optional[str] = None):
        if is_member:
            self.status_badge.setText(tr("accounts.status_member", display=display or "Actif"))
            self.status_badge.setStyleSheet(
                "background-color: #064e3b; color: #34d399; border-radius: 10px; padding: 4px 14px; font-weight: 700;"
            )
        elif is_ready:
            self.status_badge.setText(tr("accounts.status_antibot_ok"))
            self.status_badge.setStyleSheet(
                "background-color: #451a03; color: #fbbf24; border-radius: 10px; padding: 4px 14px; font-weight: 700;"
            )
        else:
            self.status_badge.setText(tr("accounts.status_unconfigured"))
            self.status_badge.setStyleSheet(
                "background-color: #334155; color: #94a3b8; border-radius: 10px; padding: 4px 14px; font-weight: 600;"
            )

    def retranslate_ui(self):
        self.title_lbl.setText(tr(self.title_key))
        self.desc_lbl.setText(tr(self.desc_key))
        self.clear_btn.setText(tr("accounts.btn_clear"))
        self.test_btn.setText(tr("accounts.btn_test"))
        self.login_btn.setText(tr("accounts.btn_login"))
