from typing import List, Optional, Tuple, Dict
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QFrame,
    QMessageBox,
    QCheckBox,
    QScrollArea,
    QWidget,
)
from PySide6.QtCore import Qt, Signal

from src.api.client import get_api_client
from src.services.requirement_reporter_service import RequirementReporterService
from src.ui.workers.report_workers import SubmitReportWorker
from src.ui.components.report_module_row import ReportModuleRowWidget
from src.i18n import tr
from src.utils.logger import logger


class ReportPreviewDialog(QDialog):
    """
    Modal dialog allowing the user to review the standardized English message
    before posting it to the mod creator's forum/page.
    Each detected requirement can be tagged as a 'missing mod' or 'not a mod (to remove)'.
    """

    report_sent = Signal(str)  # emitted with reported_at string on success
    override_changed = Signal(str, str)  # emitted with (module_title, "COMMENT" | "MOD")

    def __init__(
        self,
        mod_title: str,
        author: str,
        missing_modules: List[str],
        unnecessary_modules: Optional[List[str]] = None,
        requirements_overrides: Optional[Dict[str, str]] = None,
        source: str = "loverslab",
        page_url: str = "",
        remote_id: str = "",
        catalog_mod_id: Optional[int] = None,
        initial_message: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.mod_title = mod_title
        self.author = author or "Author"
        self.missing_modules = list(missing_modules or [])
        self.unnecessary_modules = list(unnecessary_modules or [])
        self.requirements_overrides = dict(requirements_overrides or {})
        self.source = source
        self.page_url = page_url
        self.remote_id = remote_id
        self.catalog_mod_id = catalog_mod_id
        self.initial_message = initial_message

        self.module_items: List[dict] = []
        self.module_checkboxes: List[QCheckBox] = []

        if not self.initial_message and (self.missing_modules or self.unnecessary_modules):
            self.initial_message = RequirementReporterService.build_english_message(
                self.mod_title, self.author, self.missing_modules, self.unnecessary_modules
            )

        self.setWindowTitle(tr("report_dialog.title"))
        self.resize(660, 680)
        self.setMinimumSize(580, 520)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0d111d;
                color: #f8fafc;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        # Header Title
        title_lbl = QLabel(tr("report_dialog.header"))
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #f8fafc;")
        layout.addWidget(title_lbl)

        # Subtitle info
        author_display = self.author if self.author.startswith("@") else f"@{self.author}"
        info_lbl = QLabel(
            tr("report_dialog.info", author=author_display, count=len(self.missing_modules) or len(self.unnecessary_modules))
        )
        info_lbl.setStyleSheet("font-size: 12px; color: #94a3b8; line-height: 1.4;")
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        # Missing modules summary banner with choice cards
        summary_frame = QFrame()
        summary_frame.setStyleSheet("""
            background-color: #1e1b4b;
            border: 1px solid #4f46e5;
            border-radius: 8px;
            padding: 8px 10px;
        """)
        s_layout = QVBoxLayout(summary_frame)
        s_layout.setContentsMargins(6, 6, 6, 6)
        s_layout.setSpacing(6)

        s_title = QLabel(f"📦 {tr('report_dialog.unfound_list_title')}")
        s_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #c7d2fe;")
        s_layout.addWidget(s_title)

        s_hint = QLabel(tr("report_dialog.checkbox_hint"))
        s_hint.setStyleSheet("font-size: 11px; color: #94a3b8; margin-bottom: 2px;")
        s_layout.addWidget(s_hint)

        self.module_items = []
        self.module_checkboxes = []

        all_modules = []
        seen = set()
        for m in self.missing_modules:
            if m and m not in seen:
                seen.add(m)
                is_missing = self.requirements_overrides.get(m) != "COMMENT"
                all_modules.append((m, is_missing))
        for u in self.unnecessary_modules:
            if u and u not in seen:
                seen.add(u)
                is_missing = self.requirements_overrides.get(u) == "MOD"
                all_modules.append((u, is_missing))

        # Scrollable container for module items to guarantee visibility of text edit and send button
        rows_container = QWidget()
        rows_container.setStyleSheet("background: transparent;")
        rows_layout = QVBoxLayout(rows_container)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(6)

        for mod_name, is_missing_default in all_modules:
            row_widget = ReportModuleRowWidget(mod_name, is_missing_default=is_missing_default, parent=rows_container)
            row_widget.selection_changed.connect(self._on_module_selection_changed)

            def _make_override_handler(target_name=mod_name):
                def _handler(name, override_val):
                    self.requirements_overrides[name] = override_val
                    self.override_changed.emit(name, override_val)
                return _handler

            row_widget.override_changed.connect(_make_override_handler(mod_name))

            rows_layout.addWidget(row_widget)
            self.module_checkboxes.append(row_widget.cb)
            self.module_items.append({
                "name": mod_name,
                "cb": row_widget.cb,
                "rb_missing": row_widget.rb_missing,
                "rb_unnecessary": row_widget.rb_unnecessary,
            })

        modules_scroll = QScrollArea()
        modules_scroll.setWidgetResizable(True)
        modules_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        modules_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        modules_scroll.setMaximumHeight(190)
        modules_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        modules_scroll.setWidget(rows_container)
        s_layout.addWidget(modules_scroll)

        layout.addWidget(summary_frame)

        # Message Text Edit
        msg_lbl = QLabel(tr("report_dialog.message_label"))
        msg_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #cbd5e1; margin-top: 4px;")
        layout.addWidget(msg_lbl)

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(self.initial_message)
        self.text_edit.setMinimumHeight(150)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0b0e1a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border-color: #6366f1;
            }
        """)
        layout.addWidget(self.text_edit, stretch=1)

        # Notice
        notice_lbl = QLabel(tr("report_dialog.account_notice", source=self.source.capitalize()))
        notice_lbl.setStyleSheet("font-size: 11px; color: #64748b; font-style: italic;")
        notice_lbl.setWordWrap(True)
        layout.addWidget(notice_lbl)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        self.cancel_btn = QPushButton(tr("dialogs.cancel"))
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e253b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 9px 18px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #28314d; color: #ffffff; }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.send_btn = QPushButton(tr("report_dialog.btn_send"))
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 9px 20px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #6366f1; }
            QPushButton:disabled { background-color: #3730a3; color: #94a3b8; }
        """)
        self.send_btn.clicked.connect(self._on_send_clicked)
        btn_layout.addWidget(self.send_btn)

        layout.addLayout(btn_layout)

    def _get_categorized_modules(self) -> Tuple[List[str], List[str]]:
        missing = []
        unnecessary = []
        for item in self.module_items:
            if item["cb"].isChecked():
                if item["rb_missing"].isChecked():
                    missing.append(item["name"])
                else:
                    unnecessary.append(item["name"])
        return missing, unnecessary

    def _get_selected_modules(self) -> List[str]:
        missing, unnecessary = self._get_categorized_modules()
        return missing + unnecessary

    def _on_module_selection_changed(self):
        missing, unnecessary = self._get_categorized_modules()
        if not missing and not unnecessary:
            self.send_btn.setEnabled(False)
            self.send_btn.setToolTip(tr("report_dialog.select_at_least_one"))
        else:
            self.send_btn.setEnabled(True)
            self.send_btn.setToolTip("")

        new_msg = RequirementReporterService.build_english_message(
            self.mod_title, self.author, missing, unnecessary
        )
        self.text_edit.setPlainText(new_msg)

    def _on_send_clicked(self):
        missing, unnecessary = self._get_categorized_modules()
        if not missing and not unnecessary:
            QMessageBox.warning(self, tr("dialogs.warning"), tr("report_dialog.select_at_least_one"))
            return

        message_to_send = self.text_edit.toPlainText().strip()
        if not message_to_send:
            QMessageBox.warning(self, tr("dialogs.warning"), tr("report_dialog.empty_message_error"))
            return

        self.send_btn.setEnabled(False)
        self.send_btn.setText(tr("report_dialog.sending"))
        self.cancel_btn.setEnabled(False)

        payload = {
            "catalog_mod_id": self.catalog_mod_id,
            "source": self.source,
            "remote_id": self.remote_id,
            "page_url": self.page_url,
            "title": self.mod_title,
            "author": self.author,
            "missing_modules": missing,
            "unnecessary_modules": unnecessary,
            "custom_message": message_to_send,
        }

        self.worker = SubmitReportWorker(payload, parent=self)
        self.worker.finished_result.connect(self._on_submit_finished)
        self.worker.start()

    def _on_submit_finished(self, success: bool, message: str, reported_at: str):
        self.send_btn.setEnabled(True)
        self.send_btn.setText(tr("report_dialog.btn_send"))
        self.cancel_btn.setEnabled(True)

        if success:
            if self.catalog_mod_id:
                try:
                    missing, unnecessary = self._get_categorized_modules()
                    overrides = {m: "MOD" for m in missing}
                    overrides.update({u: "COMMENT" for u in unnecessary})
                    get_api_client().save_requirements_override({
                        "catalog_mod_id": self.catalog_mod_id,
                        "overrides": overrides,
                    })
                except Exception as e:
                    logger.debug(f"Erreur enregistrement automatique des overrides après rapport: {e}")

            QMessageBox.information(
                self,
                tr("report_dialog.success_title"),
                tr("report_dialog.success_body", author=self.author),
            )
            self.report_sent.emit(reported_at or "à l'instant")
            self.accept()
        else:
            QMessageBox.warning(
                self,
                tr("report_dialog.error_title"),
                message or tr("report_dialog.generic_error"),
            )
