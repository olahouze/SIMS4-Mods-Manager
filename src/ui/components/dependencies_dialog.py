from typing import List
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QWidget,
)
from PySide6.QtCore import Qt

from src.i18n import tr


class DependenciesDialog(QDialog):
    """
    Dialog displaying the dependency tree for a mod before installation.
    Clearly shows which dependencies are already installed, which will be automatically fetched,
    and which are unfound (for partial installation).
    """

    def __init__(
        self,
        mod_title: str,
        already_installed: List[dict],
        missing: List[dict],
        unfound: List[dict] = None,
        is_partial: bool = False,
        game_dlcs: List[dict] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.mod_title = mod_title
        self.already_installed = already_installed or []
        self.missing = missing or []
        self.unfound = unfound or []
        self.game_dlcs = game_dlcs or []
        self.is_partial = is_partial or bool(self.unfound)

        self.setWindowTitle(tr("dependencies.dlg_title_partial") if self.is_partial else tr("dependencies.dlg_title_full"))
        self.setMinimumWidth(580)
        self.setMinimumHeight(440)
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0d111d;
                color: #f8fafc;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header Title
        if self.is_partial:
            title_lbl = QLabel(tr("dependencies.header_partial", title=self.mod_title))
            title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #f59e0b;")
        else:
            title_lbl = QLabel(tr("dependencies.header_full", title=self.mod_title))
            title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #f8fafc;")
        title_lbl.setWordWrap(True)
        layout.addWidget(title_lbl)

        if self.is_partial:
            info_lbl = QLabel(tr("dependencies.info_partial"))
            info_lbl.setStyleSheet("font-size: 12px; color: #fde68a; line-height: 1.4;")
        else:
            info_lbl = QLabel(tr("dependencies.info_full"))
            info_lbl.setStyleSheet("font-size: 12px; color: #94a3b8; line-height: 1.4;")
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        # Scroll area for lists
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(14)

        # 0. Official Sims 4 Game DLCs section
        if self.game_dlcs:
            dlc_header = QLabel(tr("dependencies.dlc_header", count=len(self.game_dlcs)))
            dlc_header.setStyleSheet("font-size: 13px; font-weight: 700; color: #a78bfa;")
            c_layout.addWidget(dlc_header)

            dlc_notice = QLabel(tr("dependencies.dlc_notice"))
            dlc_notice.setStyleSheet("font-size: 11px; color: #c4b5fd; margin-bottom: 2px;")
            dlc_notice.setWordWrap(True)
            c_layout.addWidget(dlc_notice)

            for dlc in self.game_dlcs:
                frame = QFrame()
                frame.setStyleSheet("""
                    background-color: #1e1b4b;
                    border: 1px solid #6366f1;
                    border-radius: 8px;
                    padding: 8px 12px;
                """)
                f_layout = QHBoxLayout(frame)
                f_layout.setContentsMargins(4, 4, 4, 4)
                dlc_title = dlc.get("title") or dlc.get("dlc_name") or "DLC Sims 4"
                is_inst = dlc.get("is_installed", False)
                stat_text = tr("dependencies.dlc_detected") if is_inst else tr("dependencies.dlc_check")
                lbl = QLabel(f"🎮 {dlc_title}")
                lbl.setStyleSheet("color: #e0e7ff; font-size: 12px; font-weight: 600;")
                badge = QLabel(stat_text)
                badge.setStyleSheet(
                    "color: #a7f3d0; font-size: 10px; font-weight: 700; padding: 2px 6px; background-color: #064e3b; border-radius: 4px;"
                    if is_inst
                    else "color: #fde68a; font-size: 10px; font-weight: 700; padding: 2px 6px; background-color: #78350f; border-radius: 4px;"
                )
                f_layout.addWidget(lbl)
                f_layout.addStretch()
                f_layout.addWidget(badge)
                c_layout.addWidget(frame)

        # 1. Unfound dependencies section (Partial install warning)
        if self.unfound:
            unf_header = QLabel(tr("dependencies.unfound_header", count=len(self.unfound)))
            unf_header.setStyleSheet("font-size: 13px; font-weight: 800; color: #f87171;")
            c_layout.addWidget(unf_header)

            for dep in self.unfound:
                frame = QFrame()
                frame.setStyleSheet("""
                    background-color: #3b141d;
                    border: 1px solid #ef4444;
                    border-radius: 8px;
                    padding: 8px 12px;
                """)
                f_layout = QHBoxLayout(frame)
                f_layout.setContentsMargins(4, 4, 4, 4)
                dep_title = dep.get("title") or f"Mod #{dep.get('remote_id')}"
                lbl = QLabel(f"⚠️ {dep_title} ({tr('dependencies.unfound_badge')})")
                lbl.setStyleSheet("color: #fca5a5; font-size: 12px; font-weight: 600;")
                f_layout.addWidget(lbl)
                c_layout.addWidget(frame)

        # 2. Already installed section (if any)
        if self.already_installed:
            ok_header = QLabel(tr("dependencies.already_header", count=len(self.already_installed)))
            ok_header.setStyleSheet("font-size: 13px; font-weight: 700; color: #34d399;")
            c_layout.addWidget(ok_header)

            for dep in self.already_installed:
                frame = QFrame()
                frame.setStyleSheet("""
                    background-color: #064e3b;
                    border: 1px solid #059669;
                    border-radius: 8px;
                    padding: 8px 12px;
                """)
                f_layout = QHBoxLayout(frame)
                f_layout.setContentsMargins(4, 4, 4, 4)
                dep_title = dep.get("title") or f"Mod #{dep.get('remote_id')}"
                lbl = QLabel(f"✓ {dep_title}")
                lbl.setStyleSheet("color: #ecfdf5; font-size: 12px; font-weight: 600;")
                f_layout.addWidget(lbl)
                c_layout.addWidget(frame)

        # 3. Missing dependencies to install (if any)
        if self.missing:
            miss_header = QLabel(tr("dependencies.missing_header", count=len(self.missing)))
            miss_header.setStyleSheet("font-size: 13px; font-weight: 700; color: #60a5fa;")
            c_layout.addWidget(miss_header)

            for dep in self.missing:
                frame = QFrame()
                frame.setStyleSheet("""
                    background-color: #1e293b;
                    border: 1px solid #3b82f6;
                    border-radius: 8px;
                    padding: 8px 12px;
                """)
                f_layout = QHBoxLayout(frame)
                f_layout.setContentsMargins(4, 4, 4, 4)
                dep_title = dep.get("title") or f"Mod #{dep.get('remote_id')}"
                lbl = QLabel(f"⬇ {dep_title}")
                lbl.setStyleSheet("color: #93c5fd; font-size: 12px; font-weight: 600;")
                f_layout.addWidget(lbl)
                c_layout.addWidget(frame)

        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        cancel_btn = QPushButton(tr("dialogs.cancel"))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e253b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #28314d; color: #ffffff; }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        if self.is_partial:
            confirm_btn = QPushButton(tr("dependencies.btn_confirm_partial"))
            confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            confirm_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d97706;
                    color: #ffffff;
                    border: 1px solid #f59e0b;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-weight: 700;
                    font-size: 13px;
                }
                QPushButton:hover { background-color: #b45309; }
            """)
        else:
            confirm_btn = QPushButton(tr("dependencies.btn_confirm_full"))
            confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            confirm_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4f46e5;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-weight: 700;
                    font-size: 13px;
                }
                QPushButton:hover { background-color: #6366f1; }
            """)
        confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)
