import webbrowser
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QFrame,
)
from PySide6.QtCore import Qt, QThread, Signal

from src.api.client import get_api_client
from src.ui.components.status_badge import StatusBadge
from src.utils.logger import logger


class DescriptionFetchWorker(QThread):
    loaded = Signal(dict)

    def __init__(self, mod_id: int):
        super().__init__()
        self.mod_id = mod_id

    def run(self):
        client = get_api_client()
        try:
            details = client.get_catalog_mod_details(self.mod_id)
            desc = details.get("description", "")
            if desc and ("<img" in desc or "<p" in desc or "<div" in desc):
                details["description"] = self._resolve_images(desc)
            self.loaded.emit(details)
        except Exception as e:
            logger.debug(f"Erreur chargement détails mod {self.mod_id}: {e}")
            self.loaded.emit({"description": "Impossible de charger la description détaillée."})

    def _resolve_images(self, html_str: str) -> str:
        """Downloads external images in background in parallel and replaces src with local file URIs."""
        try:
            from bs4 import BeautifulSoup
            from concurrent.futures import ThreadPoolExecutor
            from src.core.config import AppConfig
            from src.core.session_manager import SessionManager
            from src.utils.cache_utils import hash_url

            soup = BeautifulSoup(html_str, "html.parser")
            imgs = soup.select("img")
            if not imgs:
                return html_str

            cache_dir = AppConfig.get_desc_images_cache_dir()
            session = SessionManager.get_http_session("loverslab")

            def _detect_ext(content: bytes, fallback_ext: str) -> str:
                if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
                    return ".webp"
                if len(content) >= 4 and content[:4] == b"\x89PNG":
                    return ".png"
                if len(content) >= 3 and content[:3] == b"\xff\xd8\xff":
                    return ".jpg"
                if len(content) >= 6 and (content[:6] == b"GIF87a" or content[:6] == b"GIF89a"):
                    return ".gif"
                return fallback_ext

            # Collect unique images to download
            urls_to_fetch = set()
            for img in imgs:
                src = img.get("src")
                if src and src.startswith("http"):
                    urls_to_fetch.add(src)

            resolved_map = {}

            def _download_image(src: str):
                url_hash = hash_url(src)
                # Check if any cached file with this hash already exists
                existing_matches = list(cache_dir.glob(f"{url_hash}.*"))
                for ex in existing_matches:
                    if ex.stat().st_size > 100:
                        resolved_map[src] = ex.resolve().as_uri()
                        return

                fallback_ext = (
                    ".png"
                    if ".png" in src.lower()
                    else (".jpg" if ".jpg" in src.lower() or ".jpeg" in src.lower() else ".png")
                )

                try:
                    r = session.get(src, timeout=10)
                    if r.status_code == 200 and len(r.content) > 100:
                        real_ext = _detect_ext(r.content, fallback_ext)
                        target_file = cache_dir / f"{url_hash}{real_ext}"
                        target_file.write_bytes(r.content)
                        resolved_map[src] = target_file.resolve().as_uri()
                except Exception as err:
                    logger.debug(f"Failed to cache description image {src}: {err}")

            if urls_to_fetch:
                with ThreadPoolExecutor(max_workers=6) as pool:
                    list(pool.map(_download_image, urls_to_fetch))

            for img in imgs:
                src = img.get("src")
                if src in resolved_map:
                    img["src"] = resolved_map[src]
                img["style"] = (
                    "max-width: 95%; height: auto; border-radius: 8px; margin: 10px auto; display: block; border: 1px solid #1e293b;"
                )

            return str(soup)
        except Exception as e:
            logger.debug(f"Image resolution error: {e}")
            return html_str


class ModDetailModal(QDialog):
    """
    Overlay modal window displaying the main message and description of a mod's page
    when clicking on a catalog tile.
    """

    install_requested = Signal(dict)

    def __init__(self, mod_data: dict, is_installed: bool = False, parent=None):
        super().__init__(parent)
        self.mod_data = mod_data
        self.is_installed = is_installed
        self.setWindowTitle(mod_data.get("title", "Détails du Mod"))
        self.setMinimumSize(850, 620)
        if parent and hasattr(parent, "size") and parent.width() > 100:
            self.resize(parent.size())
        else:
            self.resize(1020, 720)

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.init_ui()
        self._load_details()

    def init_ui(self):
        # Outer container for dark rounded border styling
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(4, 4, 4, 4)

        container = QFrame()
        container.setObjectName("ModalContainer")
        container.setStyleSheet("""
            QFrame#ModalContainer {
                background-color: #0c0f1a;
                border: 2px solid #232b42;
                border-radius: 14px;
            }
        """)
        outer_layout.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # 1. Header Bar: Back button + Source Badge + Title + Close Button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        self.back_btn = QPushButton("← Retour au catalogue")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2538;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #28314d;
                color: #ffffff;
                border-color: #6366f1;
            }
        """)
        self.back_btn.clicked.connect(self.close)
        header_layout.addWidget(self.back_btn)

        source = self.mod_data.get("source", "loverslab")
        source_badge = StatusBadge(source, badge_type="source")
        header_layout.addWidget(source_badge)

        self.title_label = QLabel(self.mod_data.get("title", "Mod sans titre"))
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 800; color: #f8fafc;")
        header_layout.addWidget(self.title_label, stretch=1)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a2035;
                color: #94a3b8;
                border: 1px solid #2d3748;
                border-radius: 16px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e11d48;
                color: #ffffff;
                border-color: #f43f5e;
            }
        """)
        self.close_btn.clicked.connect(self.close)
        header_layout.addWidget(self.close_btn)

        layout.addLayout(header_layout)

        # 2. Metadata Sub-bar
        meta_layout = QHBoxLayout()
        author = self.mod_data.get("author", "Inconnu")
        self.author_label = QLabel(f"👤 Auteur : <b style='color:#60a5fa;'>{author}</b>")
        self.author_label.setStyleSheet("font-size: 13px; color: #94a3b8;")
        meta_layout.addWidget(self.author_label)

        u_date = self.mod_data.get("updated_date", "")
        if u_date:
            date_str = u_date[:10] if isinstance(u_date, str) else u_date.strftime("%d/%m/%Y")
            self.date_label = QLabel(f"📅 Mis à jour : <b style='color:#cbd5e1;'>{date_str}</b>")
            self.date_label.setStyleSheet("font-size: 13px; color: #94a3b8;")
            meta_layout.addWidget(self.date_label)

        meta_layout.addStretch()
        layout.addLayout(meta_layout)

        # 3. Tags pills
        tags = self.mod_data.get("tags", [])
        if tags:
            tags_layout = QHBoxLayout()
            tags_layout.setSpacing(6)
            for t in tags[:5]:
                t_lbl = QLabel(f"#{t}")
                t_lbl.setStyleSheet("""
                    background-color: #1e253b;
                    color: #a5b4fc;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                """)
                tags_layout.addWidget(t_lbl)
            tags_layout.addStretch()
            layout.addLayout(tags_layout)

        # Divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #1e2538;")
        layout.addWidget(divider)

        # 4. Main Description Area
        desc_header = QLabel("📄 Message Principal & Description de la page :")
        desc_header.setStyleSheet("font-size: 14px; font-weight: 700; color: #e2e8f0;")
        layout.addWidget(desc_header)

        self.desc_browser = QTextBrowser()
        self.desc_browser.setOpenExternalLinks(True)
        self.desc_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #080a12;
                color: #cbd5e1;
                border: 1px solid #1a2236;
                border-radius: 10px;
                padding: 14px;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        self.desc_browser.setPlainText("⏳ Chargement du message principal depuis la page du mod...")
        layout.addWidget(self.desc_browser, stretch=1)

        # 5. Footer Actions Bar
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(12)

        page_url = self.mod_data.get("page_url", "")
        if page_url:
            self.web_btn = QPushButton("🌐 Ouvrir la page web")
            self.web_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.web_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e2438;
                    color: #cbd5e1;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: 600;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #28314d;
                    color: #ffffff;
                }
            """)
            self.web_btn.clicked.connect(lambda: webbrowser.open(page_url))
            footer_layout.addWidget(self.web_btn)

        footer_layout.addStretch()

        # Install Button
        if self.is_installed:
            self.btn_install = QPushButton("✓ Déjà Installé")
            self.btn_install.setEnabled(False)
            self.btn_install.setStyleSheet("""
                QPushButton {
                    background-color: #064e3b;
                    color: #a7f3d0;
                    border: 1px solid #059669;
                    border-radius: 8px;
                    padding: 8px 20px;
                    font-weight: 700;
                    font-size: 12px;
                }
            """)
        else:
            self.btn_install = QPushButton("📥 Installer ce Mod")
            self.btn_install.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_install.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                    color: #ffffff;
                    border: 1px solid #818cf8;
                    border-radius: 8px;
                    padding: 8px 20px;
                    font-weight: 700;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #4f46e5);
                }
            """)
            self.btn_install.clicked.connect(self._on_install_clicked)

        footer_layout.addWidget(self.btn_install)

        # Close Button
        self.btn_close_action = QPushButton("Fermer")
        self.btn_close_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close_action.setStyleSheet("""
            QPushButton {
                background-color: #1e2438;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #28314d;
                color: #f1f5f9;
            }
        """)
        self.btn_close_action.clicked.connect(self.close)
        footer_layout.addWidget(self.btn_close_action)

        layout.addLayout(footer_layout)

    def _render_description(self, raw_content: str):
        if not raw_content:
            raw_content = "<p style='color:#64748b; font-style:italic;'>Aucune description détaillée disponible sur la page du mod.</p>"

        # Wrap in a modern dark-mode styled HTML document for QTextBrowser
        styled_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    background-color: #080a12;
                    color: #cbd5e1;
                    font-size: 13px;
                    line-height: 1.6;
                    margin: 8px;
                }}
                h1, h2, h3, h4 {{
                    color: #f8fafc;
                    margin-top: 14px;
                    margin-bottom: 8px;
                }}
                p {{
                    margin: 0 0 10px 0;
                }}
                a {{
                    color: #60a5fa;
                    text-decoration: underline;
                }}
                img {{
                    max-width: 95%;
                    height: auto;
                    border-radius: 8px;
                    margin: 10px auto;
                    display: block;
                    border: 1px solid #1e293b;
                }}
                .mod-gallery {{
                    margin-bottom: 20px;
                    padding: 14px;
                    background-color: #0d121f;
                    border: 1px solid #1e293b;
                    border-radius: 10px;
                }}
                blockquote {{
                    border-left: 3px solid #3b82f6;
                    padding-left: 10px;
                    margin-left: 0;
                    color: #94a3b8;
                }}
                ul, ol {{
                    margin-left: 20px;
                    margin-bottom: 10px;
                }}
                li {{
                    margin-bottom: 4px;
                }}
            </style>
        </head>
        <body>
            {raw_content}
        </body>
        </html>
        """
        self.desc_browser.setHtml(styled_html)

    def _load_details(self):
        mod_id = self.mod_data.get("id")
        desc = self.mod_data.get("description") or ""
        if desc and ("<p" in desc or "<div" in desc):
            self._render_description(desc)
        else:
            self.desc_browser.setHtml(
                "<p style='color:#94a3b8; font-size:13px;'>⏳ Chargement de la description et des visuels du mod...</p>"
            )

        if mod_id:
            self.worker = DescriptionFetchWorker(mod_id)
            self.worker.loaded.connect(self._on_details_loaded)
            self.worker.start()

    def _on_details_loaded(self, details: dict):
        desc = details.get("description") or ""
        self._render_description(desc)

    def _on_install_clicked(self):
        self.close()
        self.install_requested.emit(self.mod_data)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
