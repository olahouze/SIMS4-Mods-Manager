import re
from typing import List, Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QWidget,
    QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal

from src.api.client import get_api_client
from src.ui.components.report_preview_dialog import ReportPreviewDialog
from src.i18n import tr
from src.utils.logger import logger


class CheckReportStatusWorker(QThread):
    """Worker to perform live forum verification of existing user reports."""

    status_ready = Signal(dict)

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload

    def run(self):
        client = get_api_client()
        try:
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


class DependenciesDialog(QDialog):
    """
    Dialog displaying the dependency tree for a mod before installation.
    Clearly shows which dependencies are already installed, which will be automatically fetched,
    and which are unfound (for partial installation).
    Provides a button to query the forum live and notify the mod author if requirements are missing.
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

        from src.utils.game_dlc_matcher import GameDlcMatcher, SIMS4_PREFIX_REGEX

        clean_missing = []
        for d in raw_missing:
            t = (d.get("title") or "").strip()
            clean_t = re.sub(r"^[\s•\*\-\–\—\d\.\)\:\[\]\(\)\{\}\"\'\`]+", "", t).strip()
            clean_t = re.sub(
                r"(?i)^(?:requirements?|pr[ée]requis|prerequisites?|needs?|required(?:\s*(?:mods?|packs?|dlcs?))?|requires?|dlcs?|packs?)\s*[:\-–—\s]\s*",
                "",
                clean_t,
            ).strip().strip("'\"`[](){}")

            if GameDlcMatcher.is_base_game_only(clean_t):
                continue
            is_dlc = d.get("is_game_dlc") or d.get("status") == "GAME_DLC" or bool(SIMS4_PREFIX_REGEX.match(clean_t)) or GameDlcMatcher.match_dlc(clean_t)[0]
            if is_dlc:
                d["is_game_dlc"] = True
                d["status"] = "GAME_DLC"
                raw_dlcs.append(d)
            else:
                clean_missing.append(d)

        clean_unfound = []
        for d in raw_unfound:
            t = (d.get("title") or "").strip()
            clean_t = re.sub(r"^[\s•\*\-\–\—\d\.\)\:\[\]\(\)\{\}\"\'\`]+", "", t).strip()
            clean_t = re.sub(
                r"(?i)^(?:requirements?|pr[ée]requis|prerequisites?|needs?|required(?:\s*(?:mods?|packs?|dlcs?))?|requires?|dlcs?|packs?)\s*[:\-–—\s]\s*",
                "",
                clean_t,
            ).strip().strip("'\"`[](){}")

            if GameDlcMatcher.is_base_game_only(clean_t):
                continue
            is_dlc = d.get("is_game_dlc") or d.get("status") == "GAME_DLC" or bool(SIMS4_PREFIX_REGEX.match(clean_t)) or GameDlcMatcher.match_dlc(clean_t)[0]
            if is_dlc:
                d["is_game_dlc"] = True
                d["status"] = "GAME_DLC"
                raw_dlcs.append(d)
            else:
                clean_unfound.append(d)

        self.already_installed = already_installed or []
        self.missing = clean_missing
        self.unfound = clean_unfound
        self.game_dlcs = raw_dlcs
        self.is_partial = is_partial or bool(self.unfound)
        self.mod_data = mod_data or {}
        self._status_result = None
        self._check_worker = None

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

            # Forum interpellation action card (Global for all unfound dependencies of this mod)
            report_box = QFrame()
            report_box.setStyleSheet("""
                QFrame {
                    background-color: #18152e;
                    border: 1px dashed #6366f1;
                    border-radius: 8px;
                    padding: 10px 14px;
                    margin-top: 4px;
                }
            """)
            rb_layout = QHBoxLayout(report_box)
            rb_layout.setContentsMargins(4, 4, 4, 4)
            rb_layout.setSpacing(10)

            rb_info_layout = QVBoxLayout()
            rb_info_layout.setSpacing(2)
            rb_title = QLabel(f"📢 {tr('dependencies.report_author_box_title')}")
            rb_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #e0e7ff;")
            rb_desc = QLabel(tr("dependencies.report_author_box_desc"))
            rb_desc.setStyleSheet("font-size: 11px; color: #a5b4fc;")
            rb_desc.setWordWrap(True)
            rb_info_layout.addWidget(rb_title)
            rb_info_layout.addWidget(rb_desc)
            rb_layout.addLayout(rb_info_layout, stretch=1)

            self.btn_report_author = QPushButton(tr("dependencies.btn_checking_forum"))
            self.btn_report_author.setEnabled(False)
            self.btn_report_author.setCursor(Qt.CursorShape.PointingHandCursor)
            self._apply_checking_button_style()
            self.btn_report_author.clicked.connect(self._on_report_author_clicked)
            rb_layout.addWidget(self.btn_report_author)

            c_layout.addWidget(report_box)

            # Launch live forum check immediately
            self._start_live_status_check()


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

    def _apply_checking_button_style(self):
        if hasattr(self, "btn_report_author"):
            self.btn_report_author.setStyleSheet("""
                QPushButton {
                    background-color: #1e253b;
                    color: #94a3b8;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 8px 14px;
                    font-weight: 600;
                    font-size: 12px;
                }
            """)

    def _apply_already_reported_style(self):
        if hasattr(self, "btn_report_author"):
            self.btn_report_author.setStyleSheet("""
                QPushButton {
                    background-color: #064e3b;
                    color: #a7f3d0;
                    border: 1px solid #059669;
                    border-radius: 6px;
                    padding: 8px 14px;
                    font-weight: 700;
                    font-size: 12px;
                }
            """)

    def _apply_can_report_style(self):
        if hasattr(self, "btn_report_author"):
            self.btn_report_author.setStyleSheet("""
                QPushButton {
                    background-color: #4f46e5;
                    color: #ffffff;
                    border: 1px solid #6366f1;
                    border-radius: 6px;
                    padding: 8px 14px;
                    font-weight: 700;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #6366f1;
                }
            """)

    def closeEvent(self, event):
        if self._check_worker and self._check_worker.isRunning():
            self._check_worker.quit()
            self._check_worker.wait(500)
        super().closeEvent(event)

    def _start_live_status_check(self):
        missing_names = [d.get("title") or f"Mod #{d.get('remote_id')}" for d in self.unfound]
        source = self.mod_data.get("source", "loverslab")
        author = self.mod_data.get("author", "")
        has_remote = bool(
            self.mod_data.get("id")
            or self.mod_data.get("catalog_mod_id")
            or self.mod_data.get("page_url")
            or self.mod_data.get("remote_id")
        )
        if not has_remote:
            self.btn_report_author.setText(tr("dependencies.btn_report_author"))
            self._apply_can_report_style()
            self.btn_report_author.setEnabled(True)
            return

        payload = {
            "catalog_mod_id": self.mod_data.get("id") or self.mod_data.get("catalog_mod_id"),
            "source": source,
            "remote_id": str(self.mod_data.get("remote_id", "")),
            "page_url": self.mod_data.get("page_url", ""),
            "title": self.mod_title,
            "author": author,
            "missing_modules": missing_names,
        }
        self._check_worker = CheckReportStatusWorker(payload, parent=self)
        self._check_worker.status_ready.connect(self._on_status_ready)
        self._check_worker.start()


    def _on_status_ready(self, res: dict):
        self._status_result = res
        already_reported = res.get("already_reported", False)
        reported_at = res.get("reported_at")

        if not hasattr(self, "btn_report_author"):
            return

        if already_reported:
            date_display = reported_at or tr("dependencies.previously")
            self.btn_report_author.setText(tr("dependencies.btn_already_reported", date=date_display))
            self._apply_already_reported_style()
            self.btn_report_author.setEnabled(False)
            self.btn_report_author.setToolTip(tr("dependencies.already_reported_tooltip"))
        else:
            self.btn_report_author.setText(tr("dependencies.btn_report_author"))
            self._apply_can_report_style()
            self.btn_report_author.setEnabled(True)
            self.btn_report_author.setToolTip(tr("dependencies.report_author_tooltip"))

    def _on_report_author_clicked(self):
        if not self._status_result:
            return

        is_auth = self._status_result.get("is_authenticated", True)
        source = self.mod_data.get("source", "loverslab")
        if not is_auth:
            QMessageBox.warning(
                self,
                tr("dialogs.warning"),
                tr("dependencies.not_authenticated_warning", source=source.capitalize()),
            )
            return

        missing_names = [d.get("title") or f"Mod #{d.get('remote_id')}" for d in self.unfound]
        author = self._status_result.get("author") or self.mod_data.get("author", "")
        formatted_msg = self._status_result.get("formatted_message", "")
        cat_id = self.mod_data.get("id") or self.mod_data.get("catalog_mod_id")

        dlg = ReportPreviewDialog(
            mod_title=self.mod_title,
            author=author,
            missing_modules=missing_names,
            source=source,
            page_url=self.mod_data.get("page_url", ""),
            remote_id=str(self.mod_data.get("remote_id", "")),
            catalog_mod_id=cat_id,
            initial_message=formatted_msg,
            parent=self,
        )
        dlg.report_sent.connect(self._on_report_sent_success)
        dlg.exec()

    def _on_report_sent_success(self, reported_at: str):
        if hasattr(self, "btn_report_author"):
            self.btn_report_author.setText(tr("dependencies.btn_already_reported_now"))
            self._apply_already_reported_style()
            self.btn_report_author.setEnabled(False)
            self.btn_report_author.setToolTip(tr("dependencies.already_reported_tooltip"))

