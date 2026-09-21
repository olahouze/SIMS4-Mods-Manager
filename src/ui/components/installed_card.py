from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal

from src.ui.components.base_mod_card import BaseModCard
from src.ui.components.status_badge import StatusBadge
from src.ui.components.dependencies_summary_widget import DependenciesSummaryWidget
from src.i18n import tr


class InstalledCard(BaseModCard):
    """
    Premium card widget representing an installed Sims 4 mod in 'Mes Mods'.
    Matches the aesthetic quality of the catalog cards, with folder and deletion actions.
    """

    delete_requested = Signal(dict)
    open_folder_requested = Signal(str)

    def __init__(self, mod_data: dict, parent=None):
        super().__init__(mod_data, parent)
        self.thumb_width = 271
        self.thumb_height = 125

        self.setObjectName("InstalledCard")
        self.setFixedWidth(295)
        self.setFixedHeight(400)
        self.init_ui()

    def init_ui(self):
        """Exécute l'opération init ui."""
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

        # 1. Thumbnail Image Container via BaseModCard
        self.thumb_label = self._create_thumbnail_container(height=125)
        layout.addWidget(self.thumb_label)

        # 2. Source Badge & Files Count Pill
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(6)

        source = self.mod_data.get("source", "manual")
        source_badge = StatusBadge(source, badge_type="source")
        badges_layout.addWidget(source_badge)

        files_count = self.mod_data.get("files_count", 0)
        files_pill = QLabel(tr("installed.files_count", count=files_count))
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
        author = self.mod_data.get("author") or tr("common.unknown")
        inst_date = self.mod_data.get("installed_date") or ""
        date_str = (
            inst_date[:10]
            if isinstance(inst_date, str)
            else (inst_date.strftime("%d/%m/%Y") if hasattr(inst_date, "strftime") else "")
        )

        meta_lbl = QLabel(f"👤 {author}  •  📅 {date_str or tr('common.recently')}")
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
            deps_widget = DependenciesSummaryWidget(dependencies, max_show=2)
            layout.addWidget(deps_widget)

        layout.addStretch()

        # 6. Action Buttons Bar
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        # Open Folder button
        self.btn_folder = QPushButton(tr("installed.btn_folder"))
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
        self.btn_delete = QPushButton(tr("installed.btn_delete"))
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

        # Start thumbnail loading via BaseModCard
        self._load_thumbnail_async()

    def mousePressEvent(self, event):
        """Exécute l'opération mousepressevent.

        Args:
            event: Paramètre event.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.pos())
            if (hasattr(self, "btn_folder") and (child == self.btn_folder or self.btn_folder.isAncestorOf(child))) or (
                hasattr(self, "btn_delete") and (child == self.btn_delete or self.btn_delete.isAncestorOf(child))
            ):
                super().mousePressEvent(event)
                return
            self.details_requested.emit(self.mod_data)
        super().mousePressEvent(event)
