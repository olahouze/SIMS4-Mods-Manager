from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal, QThreadPool
from PySide6.QtGui import QPixmap

from src.core.config import AppConfig
from src.ui.components.image_cache import ImageCache
from src.ui.components.status_badge import StatusBadge
from src.ui.components.mod_card import ImageDownloadTask, ImageLoadSignals


class InstalledCard(QFrame):
    """
    Premium card widget representing an installed Sims 4 mod in 'Mes Mods'.
    Matches the aesthetic quality of the catalog cards, with folder and deletion actions.
    """

    delete_requested = Signal(dict)
    open_folder_requested = Signal(str)
    details_requested = Signal(dict)

    def __init__(self, mod_data: dict, parent=None):
        super().__init__(parent)
        self.mod_data = mod_data
        self.signals = ImageLoadSignals()
        self.signals.loaded.connect(self._on_image_loaded)

        self.setObjectName("InstalledCard")
        self.setFixedWidth(295)
        self.setFixedHeight(400)
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QFrame#InstalledCard {
                background-color: #131726;
                border: 1px solid #1f273d;
                border-radius: 14px;
            }
            QFrame#InstalledCard:hover {
                background-color: #161c30;
                border: 1px solid #3b82f6;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # 1. Thumbnail Image Container
        self.thumb_label = QLabel()
        self.thumb_label.setFixedHeight(125)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet("""
            background-color: #0b0d17;
            border-radius: 10px;
            border: 1px solid #1a1e32;
            color: #64748b;
            font-size: 28px;
        """)
        self.thumb_label.setText("🎮")
        layout.addWidget(self.thumb_label)

        # 2. Source Badge & Files Count Pill
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(6)

        source = self.mod_data.get("source", "manual")
        source_badge = StatusBadge(source, badge_type="source")
        badges_layout.addWidget(source_badge)

        files_count = self.mod_data.get("files_count", 0)
        files_pill = QLabel(f"📦 {files_count} fichier{'s' if files_count > 1 else ''}")
        files_pill.setStyleSheet("""
            background-color: #1e253b;
            color: #94a3b8;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 600;
        """)
        badges_layout.addWidget(files_pill)

        badges_layout.addStretch()
        layout.addLayout(badges_layout)

        # 3. Title
        title_text = self.mod_data.get("title", "Mod sans titre")
        self.title_label = QLabel(title_text)
        self.title_label.setWordWrap(True)
        self.title_label.setFixedHeight(34)
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(self.title_label)

        # 4. Author & Installation Date
        author = self.mod_data.get("author") or "Inconnu"
        inst_date = self.mod_data.get("installed_date") or ""
        date_str = (
            inst_date[:10]
            if isinstance(inst_date, str)
            else (inst_date.strftime("%d/%m/%Y") if hasattr(inst_date, "strftime") else "")
        )

        meta_lbl = QLabel(f"👤 {author}  •  📅 {date_str or 'Récemment'}")
        meta_lbl.setStyleSheet("font-size: 11px; color: #64748b;")
        layout.addWidget(meta_lbl)

        # 5. Folder Name
        folder_name = self.mod_data.get("folder_name", "")
        folder_lbl = QLabel(f"📁 {folder_name}")
        folder_lbl.setToolTip(f"Sous-dossier: {folder_name}")
        folder_lbl.setStyleSheet("font-size: 10px; color: #475569;")
        layout.addWidget(folder_lbl)

        # 6. Dependencies Box if requirements exist
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

                if is_inst or d_status == "INSTALLED":
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

        # 6. Action Buttons Bar
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        # Open Folder button
        self.btn_folder = QPushButton("📁 Dossier")
        self.btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_folder.setFixedHeight(30)
        self.btn_folder.setStyleSheet("""
            QPushButton {
                background-color: #1e2438;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 6px;
                font-weight: 600;
                font-size: 11px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #28314d;
                color: #ffffff;
            }
        """)
        self.btn_folder.clicked.connect(lambda: self.open_folder_requested.emit(folder_name))
        actions_layout.addWidget(self.btn_folder, stretch=1)

        # Delete button
        self.btn_delete = QPushButton("🗑️ Supprimer")
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.setFixedHeight(30)
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #3b1219;
                color: #fca5a5;
                border: 1px solid #7f1d1d;
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #991b1b;
                color: #ffffff;
                border-color: #dc2626;
            }
        """)
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.mod_data))
        actions_layout.addWidget(self.btn_delete, stretch=1)

        layout.addLayout(actions_layout)

        # Start thumbnail loading if available
        self._load_thumbnail_async()

    def _load_thumbnail_async(self):
        thumb_url = self.mod_data.get("thumbnail_url", "")
        if not thumb_url:
            return

        cached_pix = ImageCache.get(thumb_url)
        if cached_pix:
            scaled = cached_pix.scaled(
                271, 135, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
            )
            self.thumb_label.setPixmap(scaled)
            self.thumb_label.setText("")
            return

        source = self.mod_data.get("source", "loverslab")
        remote_id = str(self.mod_data.get("remote_id", "unknown"))
        cache_name = f"thumb_{source}_{remote_id}.jpg"
        cache_path = AppConfig.get_thumbnails_cache_dir() / cache_name

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
            thumb_url = self.mod_data.get("thumbnail_url", "")
            if thumb_url:
                ImageCache.set(thumb_url, pixmap)
            scaled = pixmap.scaled(
                271, 135, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
            )
            self.thumb_label.setPixmap(scaled)
            self.thumb_label.setText("")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.pos())
            if (hasattr(self, "btn_folder") and (child == self.btn_folder or self.btn_folder.isAncestorOf(child))) or (
                hasattr(self, "btn_delete") and (child == self.btn_delete or self.btn_delete.isAncestorOf(child))
            ):
                super().mousePressEvent(event)
                return
            self.details_requested.emit(self.mod_data)
        super().mousePressEvent(event)
