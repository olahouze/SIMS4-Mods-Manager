"""
DependenciesDialog: Modal dialog displaying the dependency tree for a mod before installation.
Uses DependencyCardWidget and AuthorInterpellateWidget for a DRY, unified UI.
"""
import threading
from typing import List, Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
)
from PySide6.QtCore import Qt

from src.api.client import get_api_client
from src.ui.components.dependency_card import DependencyCardWidget
from src.ui.components.author_interpellate_widget import AuthorInterpellateWidget
from src.services.dependency_normalizer import clean_dependency_title, detect_game_dlc_or_base_game
from src.ui.workers.report_workers import CheckReportStatusWorker as _BaseCheckReportStatusWorker
from src.i18n import tr
from src.utils.logger import logger


class CheckReportStatusWorker(_BaseCheckReportStatusWorker):
    def run(self):
        try:
            client = get_api_client()
            res = client.check_missing_report(self.payload)
            self.status_ready.emit(res)
        except Exception as e:
            logger.debug(f"CheckReportStatusWorker error: {e}")
            self.status_ready.emit({
                "can_report": True,
                "already_reported": False,
                "reported_at": None,
                "formatted_message": "",
                "author": self.payload.get("author", ""),
                "is_authenticated": True,
            })


__all__ = ["DependenciesDialog", "CheckReportStatusWorker"]


class DependenciesDialog(QDialog):
    """
    Dialog displaying the dependency tree for a mod before installation.
    Shows which dependencies are installed, which will be fetched, DLCs, and unfound/comments.
    """

    def __init__(
        self,
        mod_title: str,
        already_installed: List[dict],
        missing: List[dict],
        unfound: List[dict] = None,
        is_partial: bool = False,
        game_dlcs: List[dict] = None,
        mod_data: Optional[dict] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.mod_title = mod_title
        raw_missing = missing or []
        raw_unfound = unfound or []
        raw_dlcs = list(game_dlcs or [])

        clean_missing = []
        for d in raw_missing:
            t = (d.get("title") or "").strip()
            clean_t = clean_dependency_title(t)
            is_base, is_dlc, dlc_name, dlc_code = detect_game_dlc_or_base_game(clean_t)

            if is_base:
                d["is_game_dlc"] = True
                d["status"] = "GAME_DLC"
                d["is_installed"] = True
                d["dlc_name"] = "Jeu de base"
                if not d.get("title") or d.get("title").lower() in ["sims 4", "the sims 4"]:
                    d["title"] = "The Sims 4 (Jeu de base)"
                raw_dlcs.append(d)
                continue

            if is_dlc or d.get("is_game_dlc") or d.get("status") == "GAME_DLC":
                d["is_game_dlc"] = True
                d["status"] = "GAME_DLC"
                if dlc_name:
                    d["dlc_name"] = dlc_name
                raw_dlcs.append(d)
            else:
                clean_missing.append(d)

        self.already_installed = already_installed or []
        self.missing = clean_missing
        self.game_dlcs = raw_dlcs
        self.mod_data = dict(mod_data or {})
        self.overrides = dict(self.mod_data.get("requirements_overrides", {}) or {})

        self.unfound = []
        self.comments = []
        for d in raw_unfound:
            t = (d.get("title") or "").strip()
            if d.get("is_comment") or self.overrides.get(t) == "COMMENT":
                d["is_comment"] = True
                self.comments.append(d)
            else:
                self.unfound.append(d)

        self.is_partial = is_partial and bool(self.unfound)
        self.resize(560, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111a;
                color: #e2e8f0;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        self.title_lbl = QLabel()
        main_layout.addWidget(self.title_lbl)

        self.info_lbl = QLabel()
        self.info_lbl.setWordWrap(True)
        main_layout.addWidget(self.info_lbl)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #1e253b;
                border-radius: 8px;
                background-color: #0a0c14;
            }
        """)
        self.scroll_content = QWidget()
        self.c_layout = QVBoxLayout(self.scroll_content)
        self.c_layout.setContentsMargins(12, 12, 12, 12)
        self.c_layout.setSpacing(8)
        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll, stretch=1)

        # Author Interpellate Widget
        self.interpellate_widget = AuthorInterpellateWidget(self)
        self.interpellate_widget.override_changed.connect(self._on_dialog_override_changed)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        self.cancel_btn = QPushButton(tr("dependencies.btn_cancel"))
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e253b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #334155; color: #f8fafc; }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch()

        self.confirm_btn = QPushButton()
        self.confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.confirm_btn)
        main_layout.addLayout(btn_layout)

        self._update_dialog_header_and_buttons()
        self._render_content()

    @property
    def btn_report_author(self) -> QPushButton:
        return self.interpellate_widget.btn_report

    def _update_dialog_header_and_buttons(self):
        if self.is_partial:
            self.setWindowTitle(tr("dependencies.dlg_title_partial"))
            self.title_lbl.setText(tr("dependencies.header_partial", title=self.mod_title))
            self.title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #f59e0b;")
            self.info_lbl.setText(tr("dependencies.info_partial"))
            self.info_lbl.setStyleSheet("font-size: 12px; color: #cbd5e1; line-height: 1.4;")
            self.confirm_btn.setText(tr("dependencies.btn_confirm_partial"))
            self.confirm_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d97706; color: #ffffff;
                    border: none; border-radius: 8px;
                    padding: 10px 20px; font-weight: 700; font-size: 13px;
                }
                QPushButton:hover { background-color: #b45309; }
            """)
        else:
            self.setWindowTitle(tr("dependencies.dlg_title_full"))
            self.title_lbl.setText(tr("dependencies.header_full", title=self.mod_title))
            self.title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #f8fafc;")
            if self.comments:
                self.info_lbl.setText(tr("dependencies.all_comments_resolved"))
                self.info_lbl.setStyleSheet("font-size: 12px; color: #a7f3d0; line-height: 1.4; font-weight: 600;")
            else:
                self.info_lbl.setText(tr("dependencies.info_full"))
                self.info_lbl.setStyleSheet("font-size: 12px; color: #94a3b8; line-height: 1.4;")
            self.confirm_btn.setText(tr("dependencies.btn_confirm_full"))
            self.confirm_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4f46e5; color: #ffffff;
                    border: none; border-radius: 8px;
                    padding: 10px 20px; font-weight: 700; font-size: 13px;
                }
                QPushButton:hover { background-color: #6366f1; }
            """)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _render_content(self):
        self._clear_layout(self.c_layout)

        # 0. Official Sims 4 Game DLCs section
        if self.game_dlcs:
            dlc_header = QLabel(tr("dependencies.dlc_header", count=len(self.game_dlcs)))
            dlc_header.setStyleSheet("font-size: 13px; font-weight: 700; color: #a78bfa;")
            self.c_layout.addWidget(dlc_header)

            dlc_notice = QLabel(tr("dependencies.dlc_notice"))
            dlc_notice.setStyleSheet("font-size: 11px; color: #c4b5fd; margin-bottom: 2px;")
            dlc_notice.setWordWrap(True)
            self.c_layout.addWidget(dlc_notice)

            for dlc in self.game_dlcs:
                dlc_title = dlc.get("title") or dlc.get("dlc_name") or "DLC Sims 4"
                is_inst = dlc.get("is_installed", False)
                badge_t = tr("dependencies.dlc_detected") if is_inst else tr("dependencies.dlc_check")
                card = DependencyCardWidget(dlc_title, badge_t, badge_variant="success" if is_inst else "warning", prefix="🎮")
                self.c_layout.addWidget(card)

        # 1. Unfound dependencies section
        if self.unfound:
            unf_header = QLabel(tr("dependencies.unfound_header", count=len(self.unfound)))
            unf_header.setStyleSheet("font-size: 13px; font-weight: 800; color: #f87171;")
            self.c_layout.addWidget(unf_header)

            for dep in self.unfound:
                dep_title = dep.get("title") or f"Mod #{dep.get('remote_id')}"
                btn_comment = QPushButton(tr("dependencies.btn_mark_comment"))
                btn_comment.clicked.connect(lambda _, d=dep: self._toggle_comment(d, to_comment=True))
                card = DependencyCardWidget(
                    dep_title,
                    tr("dependencies.badge_unfound"),
                    badge_variant="danger",
                    prefix="⚠️",
                    action_btn=btn_comment,
                )
                self.c_layout.addWidget(card)

        # 2. Comments / Text Notes section
        if self.comments:
            com_header = QLabel(tr("dependencies.comments_header", count=len(self.comments)))
            com_header.setStyleSheet("font-size: 13px; font-weight: 700; color: #38bdf8; margin-top: 4px;")
            self.c_layout.addWidget(com_header)

            for dep in self.comments:
                dep_title = dep.get("title") or f"Mod #{dep.get('remote_id')}"
                btn_uncomment = QPushButton(tr("dependencies.btn_mark_mod"))
                btn_uncomment.clicked.connect(lambda _, d=dep: self._toggle_comment(d, to_comment=False))
                card = DependencyCardWidget(
                    dep_title,
                    tr("dependencies.badge_comment"),
                    badge_variant="info",
                    prefix="💬",
                    action_btn=btn_uncomment,
                )
                self.c_layout.addWidget(card)

        # Author Interpellation Button
        if self.unfound or self.comments:
            self.c_layout.addWidget(self.interpellate_widget)
            self._start_live_status_check()

        # 3. Already installed section
        if self.already_installed:
            ok_header = QLabel(tr("dependencies.already_header", count=len(self.already_installed)))
            ok_header.setStyleSheet("font-size: 13px; font-weight: 700; color: #34d399; margin-top: 6px;")
            self.c_layout.addWidget(ok_header)

            for dep in self.already_installed:
                dep_title = dep.get("title") or f"Mod #{dep.get('remote_id')}"
                card = DependencyCardWidget(dep_title, tr("dependencies.badge_installed"), badge_variant="success", prefix="✓")
                self.c_layout.addWidget(card)

        # 4. Missing dependencies to install
        if self.missing:
            miss_header = QLabel(tr("dependencies.missing_header", count=len(self.missing)))
            miss_header.setStyleSheet("font-size: 13px; font-weight: 700; color: #60a5fa; margin-top: 6px;")
            self.c_layout.addWidget(miss_header)

            for dep in self.missing:
                dep_title = dep.get("title") or f"Mod #{dep.get('remote_id')}"
                card = DependencyCardWidget(dep_title, tr("dependencies.badge_to_install"), badge_variant="info", prefix="⬇")
                self.c_layout.addWidget(card)

        self.c_layout.addStretch()

    def _start_live_status_check(self):
        missing_titles = [d.get("title") or f"Mod #{d.get('remote_id')}" for d in self.unfound]
        comment_titles = [d.get("title") or f"Mod #{d.get('remote_id')}" for d in self.comments]
        self.interpellate_widget.check_status(self.mod_data, missing_titles, comment_titles)

    def _on_status_ready(self, res: dict):
        self.interpellate_widget._on_status_ready(res)

    def _on_report_sent_success(self, reported_at: str):
        self.interpellate_widget._on_report_sent_success(reported_at)

    def _on_dialog_override_changed(self, module_title: str, override_type: str):
        for dep in list(self.unfound) + list(self.comments):
            t = (dep.get("title") or f"Mod #{dep.get('remote_id')}").strip()
            if t == module_title.strip():
                self._toggle_comment(dep, to_comment=(override_type == "COMMENT"))
                break

    def _toggle_comment(self, dep: dict, to_comment: bool):
        title = dep.get("title") or ""
        if to_comment:
            self.overrides[title] = "COMMENT"
            dep["is_comment"] = True
            if dep in self.unfound:
                self.unfound.remove(dep)
            if dep not in self.comments:
                self.comments.append(dep)
        else:
            self.overrides[title] = "MOD"
            dep["is_comment"] = False
            if dep in self.comments:
                self.comments.remove(dep)
            if dep not in self.unfound:
                self.unfound.append(dep)

        cat_id = self.mod_data.get("id") or self.mod_data.get("catalog_mod_id")
        if cat_id:
            def _async_save():
                try:
                    client = get_api_client()
                    client.save_requirements_override({
                        "catalog_mod_id": cat_id,
                        "overrides": {title: "COMMENT" if to_comment else "MOD"},
                    })
                except Exception as e:
                    logger.debug(f"Erreur enregistrement override: {e}")
            threading.Thread(target=_async_save, daemon=True).start()

        self.is_partial = bool(self.unfound)
        self._update_dialog_header_and_buttons()
        self._render_content()

    def closeEvent(self, event):
        self.interpellate_widget.cleanup()
        super().closeEvent(event)
