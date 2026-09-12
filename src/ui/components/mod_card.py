import webbrowser
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal

from src.ui.components.base_mod_card import BaseModCard
from src.ui.components.status_badge import StatusBadge


class ModCard(BaseModCard):
    """Premium Card widget representing a single mod in the unified catalog grid."""

    install_requested = Signal(dict)

    def __init__(
        self,
        mod_data: dict,
        is_installed: bool = False,
        has_update: bool = False,
        is_patreon_auth: bool = False,
        is_loverslab_auth: bool = False,
        parent=None,
    ):
        super().__init__(mod_data, parent)
        self.is_installed = is_installed
        self.has_update = has_update
        self.is_patreon_auth = is_patreon_auth
        self.is_loverslab_auth = is_loverslab_auth
        self.thumb_width = 271
        self.thumb_height = 130

        self.setObjectName("ModCard")
        self.setFixedWidth(295)
        self.setFixedHeight(410)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.init_ui()

    def init_ui(self):
        # Specific card border if installed
        if self.is_installed:
            self.setStyleSheet("""
                QFrame#ModCard {
                    background-color: #131726;
                    border: 1px solid #15803d;
                    border-radius: 14px;
                }
                QFrame#ModCard:hover {
                    background-color: #171d30;
                    border: 1px solid #22c55e;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#ModCard {
                    background-color: #131624;
                    border: 1px solid #22273d;
                    border-radius: 14px;
                }
                QFrame#ModCard:hover {
                    background-color: #171b2d;
                    border: 1px solid #6366f1;
                }
            """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # 1. Thumbnail Image Container via BaseModCard
        self.thumb_label = self._create_thumbnail_container(height=130)
        self.thumb_label.setText("📦")
        layout.addWidget(self.thumb_label)

        # 2. Badges Row
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(6)

        source = self.mod_data.get("source", "loverslab")
        badges_layout.addWidget(StatusBadge(source.capitalize(), badge_type=source))

        patreon_status = self.mod_data.get("patreon_status", "NONE")
        is_patreon_mod = (
            source == "patreon"
            or "Patreon" in self.mod_data.get("tags", [])
            or patreon_status in ["PUBLIC", "UNLOCKED", "LOCKED"]
        )

        if is_patreon_mod:
            if not self.is_patreon_auth:
                badges_layout.addWidget(StatusBadge("Patreon", badge_type="patreon"))
                badges_layout.addWidget(StatusBadge("🔒 Non connecté", badge_type="locked"))
            elif patreon_status == "PUBLIC":
                badges_layout.addWidget(StatusBadge("🔓 Public", badge_type="public"))
            elif patreon_status == "UNLOCKED":
                badges_layout.addWidget(StatusBadge("✅ Débloqué", badge_type="unlocked"))
            elif patreon_status == "LOCKED":
                tier_str = self.mod_data.get("patreon_tier") or "Verrouillé"
                badges_layout.addWidget(StatusBadge(f"🔒 {tier_str}", badge_type="locked"))

        if self.has_update:
            badges_layout.addWidget(StatusBadge("🔄 MàJ", badge_type="update"))
        elif self.is_installed:
            badges_layout.addWidget(StatusBadge("✓ Installé", badge_type="installed"))

        badges_layout.addStretch()
        layout.addLayout(badges_layout)

        # 3. Title
        title_text = self.mod_data.get("title", "Sans titre")
        self.title_label = QLabel(title_text)
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumHeight(38)
        self.title_label.setToolTip(title_text)
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc; line-height: 1.2;")
        layout.addWidget(self.title_label)

        # 4. Author & Date
        author = self.mod_data.get("author", "Inconnu")
        updated = self.mod_data.get("updated_date")
        date_str = updated.strftime("%d/%m/%Y") if updated and hasattr(updated, "strftime") else ""
        meta_label = QLabel(f"Par {author}  •  {date_str}")
        meta_label.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 500;")
        layout.addWidget(meta_label)

        # 5. Dependencies Box if requirements exist
        dependencies = self.mod_data.get("dependencies", [])
        if dependencies:
            deps_container = QFrame()
            deps_container.setStyleSheet("""
                QFrame {
                    background-color: #0b0e1a;
                    border: 1px solid #1a2035;
                    border-radius: 6px;
                    padding: 3px 6px;
                }
            """)
            deps_layout = QVBoxLayout(deps_container)
            deps_layout.setContentsMargins(4, 2, 4, 2)
            deps_layout.setSpacing(2)

            header_lbl = QLabel(f"🔗 Requis ({len(dependencies)}) :")
            header_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #94a3b8;")
            deps_layout.addWidget(header_lbl)

            max_show = 2
            for dep in dependencies[:max_show]:
                d_title = dep.get("title") if isinstance(dep, dict) else getattr(dep, "title", "Mod")
                d_status = (
                    dep.get("status") if isinstance(dep, dict) else getattr(dep, "status", "DETECTED_NOT_INSTALLED")
                )
                is_inst = dep.get("is_installed") if isinstance(dep, dict) else getattr(dep, "is_installed", False)
                is_dlc = dep.get("is_game_dlc") if isinstance(dep, dict) else getattr(dep, "is_game_dlc", False)

                if is_dlc or d_status == "GAME_DLC":
                    pill_text = f"🎮 {d_title} (DLC Sims 4)"
                    pill_style = "background-color: #3b0764; color: #d8b4fe; border: 1px solid #7e22ce;"
                elif is_inst or d_status == "INSTALLED":
                    pill_text = f"🟢 {d_title} (Installé)"
                    pill_style = "background-color: #064e3b; color: #a7f3d0; border: 1px solid #059669;"
                elif d_status == "DETECTED_NOT_INSTALLED":
                    pill_text = f"🔵 {d_title} (Détecté)"
                    pill_style = "background-color: #1e3a8a; color: #93c5fd; border: 1px solid #2563eb;"
                elif d_status == "NOT_DETECTED_SCANNING":
                    pill_text = f"🟡 {d_title} (Scan en cours)"
                    pill_style = "background-color: #451a03; color: #fde68a; border: 1px solid #d97706;"
                else:
                    pill_text = f"⚪ {d_title} (Non détecté)"
                    pill_style = "background-color: #27272a; color: #d4d4d8; border: 1px solid #52525b;"

                pill = QLabel(pill_text)
                pill.setStyleSheet(f"""
                    font-size: 9px;
                    font-weight: 600;
                    border-radius: 4px;
                    padding: 1px 4px;
                    {pill_style}
                """)
                pill.setToolTip(f"Dépendance: {d_title}\nStatut: {pill_text}")
                deps_layout.addWidget(pill)

            if len(dependencies) > max_show:
                extra_count = len(dependencies) - max_show
                more_lbl = QLabel(f"+ {extra_count} autre{'s' if extra_count > 1 else ''}...")
                more_lbl.setStyleSheet("font-size: 9px; color: #64748b; font-style: italic;")
                full_tooltip = "Dépendances complètes :\n" + "\n".join(
                    f"• {d.get('title') if isinstance(d, dict) else (d.title if hasattr(d, 'title') else str(d))}"
                    for d in dependencies
                )
                more_lbl.setToolTip(full_tooltip)
                deps_layout.addWidget(more_lbl)

            layout.addWidget(deps_container)

        layout.addStretch()

        # 5. Action Buttons Row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.action_btn = QPushButton()
        self.action_btn.setFixedHeight(34)

        # Determine Button State and Appearance
        requires_patreon = is_patreon_mod
        requires_loverslab = source == "loverslab" and not is_patreon_mod

        if self.has_update:
            # Update Available
            self.action_btn.setText("🔄 Mettre à Jour")
            self.action_btn.setEnabled(True)
            self.action_btn.setToolTip("Une version plus récente a été publiée. Cliquez pour mettre à jour.")
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d97706;
                    color: #ffffff;
                    border: 1px solid #f59e0b;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #b45309;
                }
            """)
        elif self.is_installed:
            # Already Installed (Disabled button per user request)
            self.action_btn.setText("✓ Déjà Installé")
            self.action_btn.setEnabled(False)
            self.action_btn.setToolTip("Ce mod est déjà installé dans votre jeu Sims 4.")
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #064e3b;
                    color: #a7f3d0;
                    border: 1px solid #059669;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 12px;
                }
            """)
        elif requires_loverslab and not self.is_loverslab_auth:
            # User is NOT logged in with a registered member account on LoversLab
            self.action_btn.setText("🔒 Compte LoversLab Requis")
            self.action_btn.setEnabled(False)
            self.action_btn.setToolTip(
                "LoversLab interdit le téléchargement aux invités. Vous devez renseigner votre nom d'utilisateur et mot de passe LoversLab dans l'onglet 'Comptes & Anti-Bot' pour télécharger."
            )
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3b141d;
                    color: #fca5a5;
                    border: 1px solid #7f1d1d;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 11px;
                }
            """)
        elif requires_patreon and not self.is_patreon_auth:
            # User is NOT logged in on Patreon
            self.action_btn.setText("🔒 Connexion Patreon Requise")
            self.action_btn.setEnabled(False)
            self.action_btn.setToolTip(
                "Vous devez connecter votre compte Patreon dans l'onglet 'Comptes & Anti-Bot' pour accéder à ce mod."
            )
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3b141d;
                    color: #fca5a5;
                    border: 1px solid #7f1d1d;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 11px;
                }
            """)
        elif patreon_status == "LOCKED":
            # Post requires a higher Patreon tier
            tier_text = self.mod_data.get("patreon_tier") or "Abonnement requis"
            self.action_btn.setText(f"🔒 Verrouillé ({tier_text})")
            self.action_btn.setEnabled(False)
            self.action_btn.setToolTip(
                "Ce mod nécessite un niveau d'abonnement payant Patreon non inclus dans votre compte."
            )
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2b141b;
                    color: #f87171;
                    border: 1px solid #5c1d24;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 11px;
                }
            """)
        else:
            dependencies = self.mod_data.get("dependencies", [])
            req_status = self.mod_data.get("requirements_status", "NONE")
            has_unfound_deps = (
                req_status == "PENDING_VERIFICATION"
                or any(
                    (d.get("status") if isinstance(d, dict) else getattr(d, "status", "")) in ["NOT_DETECTED_FINISHED", "NOT_DETECTED_SCANNING"]
                    and not (d.get("is_game_dlc") if isinstance(d, dict) else getattr(d, "is_game_dlc", False))
                    and (d.get("status") if isinstance(d, dict) else getattr(d, "status", "")) != "GAME_DLC"
                    for d in dependencies
                )
            )

            if has_unfound_deps:
                self.action_btn.setText("⚠️ Installation Partielle")
                self.action_btn.setEnabled(True)
                self.action_btn.setToolTip(
                    "Certaines dépendances sont introuvables sur LoversLab. Le mod peut être installé partiellement."
                )
                self.action_btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #b45309);
                        color: #ffffff;
                        border: 1px solid #f59e0b;
                        border-radius: 8px;
                        font-weight: 700;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b45309, stop:1 #92400e);
                    }
                """)
            else:
                # Ready to Install
                self.action_btn.setText("📥 Installer")
                self.action_btn.setEnabled(True)
                self.action_btn.setToolTip("Télécharger et installer ce mod dans Les Sims 4.")
                self.action_btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                        color: #ffffff;
                        border: 1px solid #818cf8;
                        border-radius: 8px;
                        font-weight: 700;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #4f46e5);
                    }
                """)

        self.action_btn.clicked.connect(lambda: self.install_requested.emit(self.mod_data))
        btn_layout.addWidget(self.action_btn, stretch=2)

        # External Link Button
        page_url = self.mod_data.get("page_url", "")
        if page_url:
            self.link_btn = QPushButton("🌐")
            self.link_btn.setToolTip(f"🌐 Ouvrir la fiche web officielle :\n{page_url}")
            self.link_btn.setFixedWidth(36)
            self.link_btn.setFixedHeight(34)
            self.link_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e2235;
                    color: #cbd5e1;
                    border: 1px solid #2e354e;
                    border-radius: 8px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #2b314c;
                    color: #ffffff;
                    border-color: #6366f1;
                }
            """)
            self.link_btn.clicked.connect(lambda: webbrowser.open(page_url))
            btn_layout.addWidget(self.link_btn)

        layout.addLayout(btn_layout)

        # Start async thumbnail loading via BaseModCard
        self._load_thumbnail_async()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.pos())
            if hasattr(self, "action_btn") and (child == self.action_btn or self.action_btn.isAncestorOf(child)):
                super().mousePressEvent(event)
                return
            self.details_requested.emit(self.mod_data)
        super().mousePressEvent(event)
