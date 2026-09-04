import webbrowser
from pathlib import Path
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, Signal, QObject, QRunnable, QThreadPool

from src.ui.components.status_badge import StatusBadge
from src.api.client import get_api_client
from src.utils.logger import logger


class ImageLoadSignals(QObject):
    loaded = Signal(str, str)  # remote_id, local_path


class ImageDownloadTask(QRunnable):
    def __init__(self, source: str, remote_id: str, url: str, dest_path: Path, signals: ImageLoadSignals):
        super().__init__()
        self.source = source
        self.remote_id = remote_id
        self.url = url
        self.dest_path = dest_path
        self.signals = signals

    def run(self):
        try:
            import httpx

            client = get_api_client()
            resp = httpx.get(
                f"{client.base_url}/api/catalog/thumbnail",
                params={"source": self.source, "remote_id": self.remote_id, "url": self.url},
                timeout=20.0,
            )
            if resp.status_code == 200 and len(resp.content) > 100:
                self.dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.dest_path, "wb") as f:
                    f.write(resp.content)
                self.signals.loaded.emit(self.remote_id, str(self.dest_path))
        except Exception as e:
            logger.debug(f"Thumbnail download failed via API for {self.url}: {e}")


class ModCard(QFrame):
    """Premium Card widget representing a single mod in the unified catalog grid."""

    install_requested = Signal(dict)
    details_requested = Signal(dict)

    def __init__(
        self,
        mod_data: dict,
        is_installed: bool = False,
        has_update: bool = False,
        is_patreon_auth: bool = False,
        is_loverslab_auth: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.mod_data = mod_data
        self.is_installed = is_installed
        self.has_update = has_update
        self.is_patreon_auth = is_patreon_auth
        self.is_loverslab_auth = is_loverslab_auth

        self.signals = ImageLoadSignals()
        self.signals.loaded.connect(self._on_image_loaded)

        self.setObjectName("ModCard")
        self.setFixedWidth(295)
        self.setFixedHeight(360)
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
        layout.setSpacing(8)

        # 1. Thumbnail Image Container
        self.thumb_label = QLabel()
        self.thumb_label.setFixedHeight(145)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet("""
            background-color: #0b0d17;
            border-radius: 10px;
            border: 1px solid #1a1e32;
            color: #475569;
            font-size: 32px;
        """)
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
        self.title_label.setMaximumHeight(42)
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

        # Start async thumbnail loading
        self._load_thumbnail_async()

    def _load_thumbnail_async(self):
        """Checks disk cache or dispatches async download task."""
        thumb_url = self.mod_data.get("thumbnail_url", "")
        if not thumb_url:
            return

        source = self.mod_data.get("source", "loverslab")
        remote_id = str(self.mod_data.get("remote_id", "unknown"))
        cache_name = f"thumb_{source}_{remote_id}.jpg"
        cache_dir = Path.home() / ".sims4_mod_manager" / "cache" / "thumbnails"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / cache_name

        if cache_path.exists() and cache_path.stat().st_size > 100:
            self._display_image(str(cache_path))
        else:
            task = ImageDownloadTask(source, remote_id, thumb_url, cache_path, self.signals)
            QThreadPool.globalInstance().start(task)

    def _on_image_loaded(self, remote_id: str, local_path: str):
        if str(self.mod_data.get("remote_id")) == remote_id:
            self._display_image(local_path)

    def _display_image(self, image_path: str):
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                271, 145, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
            )
            self.thumb_label.setPixmap(scaled)
            self.thumb_label.setText("")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.pos())
            if hasattr(self, "action_btn") and (child == self.action_btn or self.action_btn.isAncestorOf(child)):
                super().mousePressEvent(event)
                return
            self.details_requested.emit(self.mod_data)
        super().mousePressEvent(event)
