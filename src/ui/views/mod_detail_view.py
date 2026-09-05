import webbrowser
from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QTextBrowser,
    QProgressBar,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

from src.api.client import get_api_client
from src.core.config import AppConfig
from src.ui.components.status_badge import StatusBadge
from src.ui.components.image_viewer_modal import ImageViewerModal
from src.ui.workers import (
    FetchDetailsWorker,
    GalleryBatchWorker,
    GalleryThumbWorker,
    DescriptionImageLoaderWorker,
)
from src.utils.logger import logger


class ScreenshotCard(QFrame):
    clicked = Signal(int)

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setFixedSize(170, 110)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QFrame {
                background-color: #0b0f19;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
            QFrame:hover {
                border: 2px solid #6366f1;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.img_lbl = QLabel("⏳")
        self.img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_lbl.setStyleSheet("color: #64748b; font-size: 14px; border-radius: 8px;")
        layout.addWidget(self.img_lbl)

    def set_pixmap(self, pix: QPixmap):
        self.img_lbl.setPixmap(pix)
        self.img_lbl.setText("")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)
        super().mousePressEvent(event)


class ModDetailView(QWidget):
    """
    Dedicated full-page view taking 100% of the application screen
    to display rich mod details, requirements, dependencies, and actions.
    Accessible from both 'Catalogue' and 'Mes Mods'.
    """

    back_requested = Signal()
    install_requested = Signal(dict)
    uninstall_requested = Signal(dict)
    open_folder_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.mod_data: Dict[str, Any] = {}
        self.origin_name: str = "Catalogue"
        self.origin_index: int = 1
        self.is_installed: bool = False
        self.has_update: bool = False
        self._current_load_id: int = 0
        self.main_scroll: Optional[QScrollArea] = None
        self.worker: Optional[FetchDetailsWorker] = None
        self.screenshots: List[str] = []
        self.gallery_batch_worker: Optional[GalleryBatchWorker] = None
        self.gallery_workers: List[GalleryThumbWorker] = []
        self.desc_img_worker: Optional[DescriptionImageLoaderWorker] = None
        self.cache_dir = AppConfig.get_screenshots_cache_dir()

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # 1. Top Navigation Bar (Back Button + Mod Title + Origin context)
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(14)

        self.back_btn = QPushButton("← Retour")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2438;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2e3856;
                color: #ffffff;
                border-color: #6366f1;
            }
        """)
        self.back_btn.clicked.connect(self._on_back_clicked)
        nav_layout.addWidget(self.back_btn)

        self.title_lbl = QLabel("Détails du Mod")
        self.title_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #f8fafc;")
        nav_layout.addWidget(self.title_lbl, stretch=1)

        self.source_badge = StatusBadge("LoversLab", badge_type="source")
        nav_layout.addWidget(self.source_badge)

        self.installed_badge = StatusBadge("Installé", badge_type="install")
        nav_layout.addWidget(self.installed_badge)

        main_layout.addLayout(nav_layout)

        # 2. Main Scrollable Container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")
        self.main_scroll = scroll

        self.content_widget = QWidget()
        self.c_layout = QVBoxLayout(self.content_widget)
        self.c_layout.setContentsMargins(0, 0, 0, 0)
        self.c_layout.setSpacing(16)

        # Hero Meta Panel (Author, version, date, actions)
        self.hero_card = QFrame()
        self.hero_card.setStyleSheet("""
            QFrame {
                background-color: #131726;
                border: 1px solid #1f273d;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        hero_layout = QHBoxLayout(self.hero_card)
        hero_layout.setSpacing(18)

        # Thumbnail
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(140, 95)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet("""
            background-color: #0b0d17;
            border-radius: 8px;
            border: 1px solid #1a1e32;
            color: #64748b;
            font-size: 24px;
        """)
        self.thumb_label.setText("🎮")
        hero_layout.addWidget(self.thumb_label)

        # Meta Details
        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(6)

        self.meta_author = QLabel("👤 Auteur : Inconnu")
        self.meta_author.setStyleSheet("font-size: 13px; color: #cbd5e1; font-weight: 600;")
        meta_layout.addWidget(self.meta_author)

        self.meta_date = QLabel("📅 Date de mise à jour : Inconnue")
        self.meta_date.setStyleSheet("font-size: 12px; color: #94a3b8;")
        meta_layout.addWidget(self.meta_date)

        self.meta_tags = QLabel("🏷️ Tags : Aucun")
        self.meta_tags.setStyleSheet("font-size: 11px; color: #64748b;")
        self.meta_tags.setWordWrap(True)
        meta_layout.addWidget(self.meta_tags)

        hero_layout.addLayout(meta_layout, stretch=2)

        # Action Buttons on Right Side
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(10)
        actions_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.install_btn = QPushButton("📥 Installer")
        self.install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_btn.setFixedHeight(38)
        self.install_btn.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-weight: 700;
                font-size: 13px;
                padding: 8px 20px;
            }
            QPushButton:hover { background-color: #6366f1; }
        """)
        self.install_btn.clicked.connect(self._on_install_clicked)
        actions_layout.addWidget(self.install_btn)

        self.open_folder_btn = QPushButton("📁 Ouvrir le dossier")
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.setFixedHeight(34)
        self.open_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2438;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
                padding: 6px 14px;
            }
            QPushButton:hover { background-color: #28314d; color: #ffffff; }
        """)
        self.open_folder_btn.clicked.connect(self._on_open_folder_clicked)
        actions_layout.addWidget(self.open_folder_btn)

        self.web_btn = QPushButton("🌐 Page Officielle")
        self.web_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.web_btn.setFixedHeight(34)
        self.web_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2438;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
                padding: 6px 14px;
            }
            QPushButton:hover { background-color: #28314d; color: #ffffff; }
        """)
        self.web_btn.clicked.connect(self._on_web_clicked)
        actions_layout.addWidget(self.web_btn)

        hero_layout.addLayout(actions_layout)
        self.c_layout.addWidget(self.hero_card)

        # 3. Requirements & Dependencies Section
        self.req_frame = QFrame()
        self.req_frame.setStyleSheet("""
            QFrame {
                background-color: #101424;
                border: 1px solid #232d45;
                border-radius: 12px;
                padding: 14px 18px;
            }
        """)
        self.req_layout = QVBoxLayout(self.req_frame)
        self.req_layout.setSpacing(10)

        # Retractable header with title and toggle button
        req_header = QHBoxLayout()
        req_header.setContentsMargins(0, 0, 0, 0)
        self.req_title = QLabel("🔗 Dépendances & Prérequis (Requirements) :")
        self.req_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #f8fafc;")
        req_header.addWidget(self.req_title, stretch=1)

        self.req_collapse_btn = QPushButton("▲ Réduire")
        self.req_collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.req_collapse_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #f1f5f9;
            }
        """)
        self.req_collapse_btn.clicked.connect(self._toggle_requirements_collapse)
        req_header.addWidget(self.req_collapse_btn)
        self.req_layout.addLayout(req_header)

        # Retractable body container
        self.req_body = QWidget()
        self.req_body_layout = QVBoxLayout(self.req_body)
        self.req_body_layout.setContentsMargins(0, 0, 0, 0)
        self.req_body_layout.setSpacing(8)

        self.req_desc = QLabel()
        self.req_desc.setWordWrap(True)
        self.req_desc.setStyleSheet("font-size: 12px; color: #cbd5e1;")
        self.req_body_layout.addWidget(self.req_desc)

        self.deps_container = QWidget()
        self.deps_layout = QVBoxLayout(self.deps_container)
        self.deps_layout.setContentsMargins(0, 4, 0, 0)
        self.deps_layout.setSpacing(8)
        self.req_body_layout.addWidget(self.deps_container)

        self.req_layout.addWidget(self.req_body)
        self.c_layout.addWidget(self.req_frame)

        # 4. Screenshot Gallery Section (Dedicated Horizontal Strip)
        self.gallery_frame = QFrame()
        self.gallery_frame.setObjectName("GalleryFrame")
        self.gallery_frame.setVisible(False)
        self.gallery_frame.setStyleSheet("""
            QFrame#GalleryFrame {
                background-color: #0f1423;
                border: 1px solid #1e293b;
                border-radius: 12px;
                padding: 14px 16px;
            }
        """)
        g_box = QVBoxLayout(self.gallery_frame)
        g_box.setContentsMargins(0, 0, 0, 0)
        g_box.setSpacing(10)

        g_hdr = QHBoxLayout()
        self.gallery_title = QLabel("📸 Galerie & Captures d'écran :")
        self.gallery_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #93c5fd;")
        g_hdr.addWidget(self.gallery_title)

        hint_lbl = QLabel("(Cliquez sur une image pour l'agrandir en haute définition)")
        hint_lbl.setStyleSheet("font-size: 11px; color: #64748b;")
        g_hdr.addWidget(hint_lbl)
        g_hdr.addStretch()
        g_box.addLayout(g_hdr)

        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setFixedHeight(128)
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.gallery_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.gallery_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:horizontal {
                height: 6px;
                background: #0b0f19;
                border-radius: 3px;
            }
            QScrollBar::handle:horizontal {
                background: #334155;
                border-radius: 3px;
                min-width: 25px;
            }
        """)
        self.gallery_container = QWidget()
        self.gallery_container.setStyleSheet("background: transparent;")
        self.gallery_cards_layout = QHBoxLayout(self.gallery_container)
        self.gallery_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery_cards_layout.setSpacing(10)
        self.gallery_cards_layout.addStretch()
        self.gallery_scroll.setWidget(self.gallery_container)
        g_box.addWidget(self.gallery_scroll)

        self.c_layout.addWidget(self.gallery_frame)

        # Loading Progress Bar
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setFixedHeight(6)
        self.loading_bar.setStyleSheet("""
            QProgressBar { background-color: #1e293b; border-radius: 3px; }
            QProgressBar::chunk { background-color: #6366f1; border-radius: 3px; }
        """)
        self.c_layout.addWidget(self.loading_bar)

        # 5. Description HTML View
        self.desc_browser = QTextBrowser()
        self.desc_browser.setOpenExternalLinks(True)
        self.desc_browser.setMinimumHeight(450)
        self.desc_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #0b0e18;
                color: #e2e8f0;
                border: 1px solid #1a2235;
                border-radius: 12px;
                padding: 18px;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        self.c_layout.addWidget(self.desc_browser, stretch=1)

        scroll.setWidget(self.content_widget)
        main_layout.addWidget(scroll, stretch=1)

    def load_mod(self, mod_data: dict, origin_name: str = "Catalogue", origin_index: int = 1):
        """Loads and displays mod details, initiating background fetch for rich content, gallery, and dependencies."""
        self._current_load_id += 1
        current_load_id = self._current_load_id

        self.mod_data = mod_data
        self.origin_name = origin_name
        self.origin_index = origin_index
        self.back_btn.setText(f"← Retour à {origin_name}")

        title = mod_data.get("title", "Détails du Mod")
        self.title_lbl.setText(title)

        author = mod_data.get("author") or "Inconnu"
        self.meta_author.setText(f"👤 Auteur : {author}")

        date_val = mod_data.get("updated_date") or mod_data.get("installed_date") or ""
        date_str = str(date_val)[:10] if date_val else "Non renseignée"
        self.meta_date.setText(f"📅 Mise à jour : {date_str}")

        tags = mod_data.get("tags") or []
        tags_str = ", ".join(tags) if tags else "Aucun tag"
        self.meta_tags.setText(f"🏷️ Tags : {tags_str}")

        source = mod_data.get("source", "loverslab")
        self.source_badge.setText(source.capitalize())

        # Determine installation state
        self.is_installed = bool(mod_data.get("is_installed", False) or mod_data.get("folder_name"))
        self.has_update = bool(mod_data.get("has_update", False))

        if self.is_installed:
            self.installed_badge.setText("✓ Installé")
            self.installed_badge.setStyleSheet(
                "background-color: #064e3b; color: #34d399; border-radius: 10px; padding: 4px 12px; font-weight: 700;"
            )
            self.open_folder_btn.setVisible(True)
            if self.has_update:
                self.install_btn.setText("🔄 Mettre à jour")
                self.install_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f59e0b;
                        color: #ffffff;
                        border: none;
                        border-radius: 8px;
                        font-weight: 700;
                        font-size: 13px;
                        padding: 8px 20px;
                    }
                    QPushButton:hover { background-color: #d97706; }
                """)
            else:
                self.install_btn.setText("✓ Déjà Installé")
                self.install_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1e293b;
                        color: #94a3b8;
                        border: 1px solid #334155;
                        border-radius: 8px;
                        font-weight: 600;
                        font-size: 13px;
                        padding: 8px 20px;
                    }
                """)
        else:
            self.installed_badge.setText("Non installé")
            self.installed_badge.setStyleSheet(
                "background-color: #1e293b; color: #94a3b8; border-radius: 10px; padding: 4px 12px; font-weight: 600;"
            )
            self.open_folder_btn.setVisible(False)
            self.install_btn.setText("📥 Installer le mod")
            self.install_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4f46e5;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 13px;
                    padding: 8px 20px;
                }
                QPushButton:hover { background-color: #6366f1; }
            """)

        # 1. Reset scroll position immediately to top
        if self.main_scroll:
            self.main_scroll.verticalScrollBar().setValue(0)

        # 2. Reset description view immediately with clean loading skeleton (erases previous mod's description)
        self.desc_browser.setHtml("""
            <div style='text-align: center; padding: 60px 20px; color: #64748b; font-family: sans-serif;'>
                <div style='font-size: 32px; margin-bottom: 12px;'>⏳</div>
                <div style='font-size: 15px; font-weight: 700; color: #94a3b8;'>Chargement des détails et de la description...</div>
                <div style='font-size: 12px; margin-top: 6px; color: #475569;'>Inspection des prérequis et des galeries d'images</div>
            </div>
        """)

        # 3. Reset and load thumbnail
        self._load_local_thumbnail()

        # 4. Render initial requirements state if already present in mod_data, or show loading state
        if mod_data.get("requirements_status") == "RESOLVED" and mod_data.get("dependencies"):
            self._render_requirements(mod_data)
        else:
            self._set_requirements_loading()

        # 5. Clear and hide existing gallery immediately
        self.screenshots = []
        self._clear_gallery()
        self.gallery_frame.setVisible(False)

        # 6. Stop and disconnect previous background workers cleanly
        if self.worker and self.worker.isRunning():
            try:
                self.worker.finished.disconnect()
                self.worker.failed.disconnect()
            except Exception:
                pass
            self.worker.terminate()
            self.worker = None

        if self.desc_img_worker and self.desc_img_worker.isRunning():
            self.desc_img_worker.cancel()
            self.desc_img_worker.terminate()
            self.desc_img_worker = None

        if self.gallery_batch_worker and self.gallery_batch_worker.isRunning():
            self.gallery_batch_worker.cancel()
            self.gallery_batch_worker.terminate()
            self.gallery_batch_worker = None

        # 7. Trigger background fetch with load_id guard
        self.loading_bar.setVisible(True)
        mod_id = mod_data.get("id") or mod_data.get("catalog_mod_id")
        page_url = mod_data.get("page_url", "")
        remote_id = str(mod_data.get("remote_id", ""))

        self.worker = FetchDetailsWorker(mod_id, page_url, source, remote_id, load_id=current_load_id)
        self.worker.finished.connect(lambda data, lid=current_load_id: self._on_details_fetched(data, lid))
        self.worker.failed.connect(lambda err, lid=current_load_id: self._on_details_failed(err, lid))
        self.worker.start()


    def _toggle_requirements_collapse(self):
        """Toggles visibility of the requirements body (collapse / expand)."""
        is_collapsed = self.req_body.isHidden()
        self.req_body.setVisible(is_collapsed)
        if is_collapsed:
            self.req_collapse_btn.setText("▲ Réduire")
        else:
            self.req_collapse_btn.setText("▼ Développer")

    def _set_requirements_loading(self):
        """Displays an informative loading message in the requirements section while analysis is running."""
        self.req_frame.setVisible(True)
        self.req_collapse_btn.setVisible(True)
        self.req_collapse_btn.setText("▲ Réduire")
        self.req_body.setVisible(True)
        self.req_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 12px;
                padding: 14px 18px;
            }
        """)
        self.req_title.setText("🔄 Analyse des dépendances et prérequis...")
        self.req_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #94a3b8;")
        self.req_desc.setText(
            "Analyse en cours des prérequis du mod et vérification des dépendances sur LoversLab...\n"
            "Veuillez patienter pendant l'inspection des données."
        )
        while self.deps_layout.count():
            it = self.deps_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def _render_requirements(self, data: dict):
        """Displays requirements status, dependencies list, or blocking warning."""
        req_text = data.get("requirements_text")
        req_status = data.get("requirements_status", "NONE")
        dependencies = data.get("dependencies", [])

        # Clear existing dependency widgets
        while self.deps_layout.count():
            it = self.deps_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        self.req_collapse_btn.setText("▼ Développer" if self.req_body.isHidden() else "▲ Réduire")

        has_unfound_deps = (
            req_status == "PENDING_VERIFICATION"
            or any(
                (d.get("status") if isinstance(d, dict) else getattr(d, "status", ""))
                in ["NOT_DETECTED_FINISHED", "NOT_DETECTED_SCANNING"]
                for d in dependencies
            )
        )

        if has_unfound_deps:
            self.req_frame.setVisible(True)
            self.req_frame.setStyleSheet("""
                QFrame {
                    background-color: #2b180a;
                    border: 1px solid #d97706;
                    border-radius: 12px;
                    padding: 16px;
                }
            """)
            self.req_title.setText("⚠️ Dépendances partiellement disponibles (Installation partielle autorisée)")
            self.req_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #fde68a;")
            self.req_desc.setText(
                f"Ce mod indique des dépendances dont certaines ne sont pas disponibles sur LoversLab :\n"
                f"« {req_text or 'Prérequis textuels non résolus'} »\n\n"
                f"L'installation partielle est autorisée. Le mod principal et ses dépendances trouvées seront installés, "
                f"mais certaines fonctionnalités risquent de ne pas fonctionner correctement sans les composants manquants."
            )

            # Also render any identified dependencies if present
            for dep in dependencies:
                d_frame = QFrame()
                d_frame.setStyleSheet("""
                    background-color: #1e293b;
                    border-radius: 6px;
                    padding: 6px 12px;
                """)
                df_layout = QHBoxLayout(d_frame)
                df_layout.setContentsMargins(4, 4, 4, 4)

                d_title = dep.get("title") or f"Mod #{dep.get('remote_id')}"
                is_inst = dep.get("is_installed", False)
                d_st = dep.get("status", "DETECTED_NOT_INSTALLED")
                if is_inst or d_st == "INSTALLED":
                    status_txt = "✅ Déjà installé"
                    status_color = "#34d399"
                elif d_st == "DETECTED_NOT_INSTALLED":
                    status_txt = "📥 Sera installé"
                    status_color = "#60a5fa"
                else:
                    status_txt = "⚠️ Introuvable"
                    status_color = "#f87171"

                lbl_name = QLabel(f"• {d_title}")
                lbl_name.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: 600;")
                df_layout.addWidget(lbl_name, stretch=1)

                lbl_st = QLabel(status_txt)
                lbl_st.setStyleSheet(f"color: {status_color}; font-size: 11px; font-weight: 700;")
                df_layout.addWidget(lbl_st)

                self.deps_layout.addWidget(d_frame)

            if not self.is_installed:
                self.install_btn.setEnabled(True)
                self.install_btn.setText("⚠️ Installation Partielle")
                self.install_btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #b45309);
                        color: #ffffff;
                        border: 1px solid #f59e0b;
                        border-radius: 8px;
                        font-weight: 700;
                        font-size: 13px;
                        padding: 8px 20px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b45309, stop:1 #92400e);
                    }
                """)

        elif req_status == "RESOLVED" and dependencies:
            self.req_frame.setVisible(True)
            self.req_frame.setStyleSheet("""
                QFrame {
                    background-color: #10192e;
                    border: 1px solid #3b82f6;
                    border-radius: 12px;
                    padding: 16px;
                }
            """)
            self.req_title.setText(f"🔗 Dépendances LoversLab identifiées ({len(dependencies)}) :")
            self.req_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #93c5fd;")
            self.req_desc.setText(
                "Ce mod s'appuie sur les composants suivants. Lors de l'installation, les dépendances manquantes "
                "seront automatiquement téléchargées et installées :"
            )
            for dep in dependencies:
                d_frame = QFrame()
                d_frame.setStyleSheet("""
                    background-color: #1e293b;
                    border-radius: 6px;
                    padding: 6px 12px;
                """)
                df_layout = QHBoxLayout(d_frame)
                df_layout.setContentsMargins(4, 4, 4, 4)

                d_title = dep.get("title") or f"Mod #{dep.get('remote_id')}"
                is_inst = dep.get("is_installed", False)
                status_txt = "✅ Déjà installé" if is_inst else "📥 Sera installé automatiquement"
                status_color = "#34d399" if is_inst else "#60a5fa"

                lbl_name = QLabel(f"• {d_title}")
                lbl_name.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: 600;")
                df_layout.addWidget(lbl_name, stretch=1)

                lbl_st = QLabel(status_txt)
                lbl_st.setStyleSheet(f"color: {status_color}; font-size: 11px; font-weight: 700;")
                df_layout.addWidget(lbl_st)

                self.deps_layout.addWidget(d_frame)

            if not self.is_installed:
                self.install_btn.setEnabled(True)
                self.install_btn.setText("📥 Installer (+ Dépendances)")
                self.install_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #4f46e5;
                        color: #ffffff;
                        border: none;
                        border-radius: 8px;
                        font-weight: 700;
                        font-size: 13px;
                        padding: 8px 20px;
                    }
                    QPushButton:hover { background-color: #6366f1; }
                """)

        else:
            if req_text and req_text.strip():
                self.req_frame.setVisible(True)
                self.req_collapse_btn.setVisible(True)
                self.req_collapse_btn.setText("▲ Réduire" if self.req_body.isVisible() else "▼ Développer")
                self.req_frame.setStyleSheet("""
                    QFrame {
                        background-color: #101424;
                        border: 1px solid #232d45;
                        border-radius: 12px;
                        padding: 14px 18px;
                    }
                """)
                self.req_title.setText("ℹ️ Notes de prérequis :")
                self.req_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #cbd5e1;")
                self.req_desc.setText(req_text)
            else:
                self.req_frame.setVisible(False)

    def _on_details_fetched(self, full_details: dict, load_id: Optional[int] = None):
        if load_id is not None and load_id != self._current_load_id:
            logger.debug(f"Ignoring obsolete details fetched for load_id={load_id} (current={self._current_load_id})")
            return

        self.loading_bar.setVisible(False)
        self._render_requirements(full_details)

        # 1. Render Screenshots Gallery in parallel via GalleryBatchWorker
        self.screenshots = full_details.get("screenshots", [])
        self._render_gallery(self.screenshots)

        # 2. Render HTML Description with asynchronous image downloader
        desc = full_details.get("description", "")
        if not desc:
            desc = "<p style='color:#94a3b8;'>Aucune description disponible pour ce mod.</p>"
        self._render_description(desc)

    def _on_details_failed(self, err_msg: str, load_id: Optional[int] = None):
        if load_id is not None and load_id != self._current_load_id:
            return

        self.loading_bar.setVisible(False)
        logger.debug(f"Details fetch error in ModDetailView: {err_msg}")
        self.desc_browser.setHtml(
            f"<p style='color:#94a3b8;'>Impossible de charger la description en ligne ({err_msg}).</p>"
        )
        if "Analyse des dépendances" in self.req_title.text():
            self.req_frame.setVisible(False)

    def _render_gallery(self, screenshots: List[str]):
        """Populates horizontal scroll area with screenshot thumbnail cards using parallel GalleryBatchWorker."""
        self._clear_gallery()
        if not screenshots:
            self.gallery_frame.setVisible(False)
            return

        self.gallery_frame.setVisible(True)
        self.gallery_title.setText(f"📸 Galerie & Captures d'écran ({len(screenshots)}) :")

        for idx in range(len(screenshots)):
            card = ScreenshotCard(idx, self)
            card.clicked.connect(self._open_image_viewer)
            # Insert before the stretch item
            insert_pos = max(0, self.gallery_cards_layout.count() - 1)
            self.gallery_cards_layout.insertWidget(insert_pos, card)

        self.gallery_batch_worker = GalleryBatchWorker(screenshots, self.cache_dir, load_id=self._current_load_id)
        self.gallery_batch_worker.thumb_ready.connect(self._on_gallery_thumb_ready)
        self.gallery_batch_worker.start()

    def _on_gallery_thumb_ready(self, index: int, pix: QPixmap):
        for i in range(self.gallery_cards_layout.count()):
            it = self.gallery_cards_layout.itemAt(i)
            if it and it.widget() and isinstance(it.widget(), ScreenshotCard):
                if it.widget().index == index:
                    it.widget().set_pixmap(pix)
                    break

    def _clear_gallery(self):
        if self.gallery_batch_worker and self.gallery_batch_worker.isRunning():
            self.gallery_batch_worker.cancel()
            self.gallery_batch_worker.terminate()
        self.gallery_batch_worker = None

        for w in self.gallery_workers:
            if w.isRunning():
                w.terminate()
        self.gallery_workers.clear()

        # Remove cards except the stretch item
        while self.gallery_cards_layout.count() > 1:
            it = self.gallery_cards_layout.takeAt(0)
            if it and it.widget():
                it.widget().deleteLater()

    def _open_image_viewer(self, index: int):
        if not self.screenshots:
            return
        dlg = ImageViewerModal(self.screenshots, current_index=index, parent=self)
        dlg.exec()

    def _render_description(self, raw_html: str):
        """Displays description and downloads remote images to local cache for rich rendering."""
        # Initial display
        self.desc_browser.setHtml(raw_html)

        if self.desc_img_worker and self.desc_img_worker.isRunning():
            self.desc_img_worker.cancel()
            self.desc_img_worker.terminate()

        self.desc_img_worker = DescriptionImageLoaderWorker(raw_html)
        self.desc_img_worker.images_updated.connect(self._on_desc_images_updated)
        self.desc_img_worker.start()

    def _on_desc_images_updated(self, updated_html: str):
        v_bar = self.desc_browser.verticalScrollBar()
        scroll_pos = v_bar.value()
        self.desc_browser.setHtml(updated_html)
        v_bar.setValue(scroll_pos)

    def _load_local_thumbnail(self):
        source = self.mod_data.get("source", "loverslab")
        remote_id = str(self.mod_data.get("remote_id", "unknown"))
        cache_path = AppConfig.get_thumbnails_cache_dir() / f"thumb_{source}_{remote_id}.jpg"
        if cache_path.exists():
            pix = QPixmap(str(cache_path))
            if not pix.isNull():
                self.thumb_label.setPixmap(
                    pix.scaled(140, 95, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                )
                self.thumb_label.setText("")
                return
        self.thumb_label.setPixmap(QPixmap())
        self.thumb_label.setText("🎮")


    def _on_back_clicked(self):
        self.back_requested.emit()

    def _on_install_clicked(self):
        self.install_requested.emit(self.mod_data)

    def _on_open_folder_clicked(self):
        folder = self.mod_data.get("folder_name", "")
        if folder:
            self.open_folder_requested.emit(folder)

    def _on_web_clicked(self):
        url = self.mod_data.get("page_url", "")
        if url:
            webbrowser.open(url)
