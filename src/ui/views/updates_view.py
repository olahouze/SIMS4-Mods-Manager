from typing import Optional, List, Dict, Any
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QHeaderView,
    QMessageBox,
    QCheckBox,
    QLineEdit,
)
from PySide6.QtCore import QThread, Signal, Qt

from src.api.client import get_api_client
from src.ui.components.status_badge import StatusBadge
from src.ui.components.progress_dialog import ProgressDialog
from src.i18n import tr
from src.utils.logger import logger


class UpdateWorker(QThread):
    finished = Signal(bool, str)

    def __init__(
        self,
        mode: str = "single",
        installed_id: Optional[int] = None,
        installed_ids: Optional[List[int]] = None,
    ):
        super().__init__()
        self.mode = mode
        self.installed_id = installed_id
        self.installed_ids = installed_ids or []

    def run(self):
        client = get_api_client()
        try:
            if self.mode == "single" and self.installed_id:
                res = client.update_mod(self.installed_id)
            elif self.mode == "batch" and self.installed_ids:
                res = client.update_selected_mods(self.installed_ids)
            else:
                res = client.update_all_mods()
            self.finished.emit(res.get("success", False), res.get("message", ""))
        except Exception as e:
            self.finished.emit(False, f"Erreur API lors de la mise à jour: {e}")


class UpdatesView(QWidget):
    """
    Spacious modern view displaying all installed mods with current and new versions,
    individual update buttons, selection checkboxes, and batch update capabilities.
    """

    ROW_HEIGHT = 68
    updates_applied = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.all_mods: List[Dict[str, Any]] = []
        self.checkbox_items: List[tuple[int, str, QCheckBox, bool]] = []
        self._updatable_count: int = 0
        self._total_installed: int = 0
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Header Bar: Stats & Main Actions
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        header_title_layout = QVBoxLayout()
        header_title_layout.setSpacing(4)

        self.main_title = QLabel(tr("updates.title"))
        self.main_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #f8fafc;")
        header_title_layout.addWidget(self.main_title)

        self.counter_label = QLabel(tr("updates.searching"))
        self.counter_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #94a3b8;")
        header_title_layout.addWidget(self.counter_label)

        header_layout.addLayout(header_title_layout)
        header_layout.addStretch()

        self.refresh_btn = QPushButton(tr("updates.refresh_btn"))
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2238;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
                min-height: 22px;
            }
            QPushButton:hover { background-color: #2a2f4c; border-color: #6366f1; }
        """)
        self.refresh_btn.clicked.connect(self.refresh_updates)
        header_layout.addWidget(self.refresh_btn)

        self.update_selected_btn = QPushButton(tr("updates.update_selected_btn", count=0))
        self.update_selected_btn.setEnabled(False)
        self.update_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: 700;
                font-size: 13px;
                min-height: 22px;
            }
            QPushButton:hover { background-color: #6366f1; }
            QPushButton:disabled {
                background-color: #1e2238;
                color: #475569;
                border: 1px solid #282e44;
            }
        """)
        self.update_selected_btn.clicked.connect(self.update_selected_mods)
        header_layout.addWidget(self.update_selected_btn)

        self.update_all_btn = QPushButton(tr("updates.update_all_btn"))
        self.update_all_btn.setEnabled(False)
        self.update_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #eab308;
                color: #000000;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: 700;
                font-size: 13px;
                min-height: 22px;
            }
            QPushButton:hover { background-color: #facc15; }
            QPushButton:disabled {
                background-color: #1e2238;
                color: #475569;
                border: 1px solid #282e44;
            }
        """)
        self.update_all_btn.clicked.connect(self.update_all_mods)
        header_layout.addWidget(self.update_all_btn)

        layout.addLayout(header_layout)

        # 2. Controls & Search Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(10)

        self.select_updates_btn = QPushButton(tr("updates.select_updates_btn"))
        self.select_updates_btn.setToolTip(tr("updates.select_updates_tip"))
        self.select_updates_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2238;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #0369a1; color: #ffffff; }
        """)
        self.select_updates_btn.clicked.connect(self.select_updates_only)
        toolbar_layout.addWidget(self.select_updates_btn)

        self.select_all_btn = QPushButton(tr("updates.select_all_btn"))
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2238;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2a2f4c; color: #ffffff; }
        """)
        self.select_all_btn.clicked.connect(self.select_all)
        toolbar_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton(tr("updates.deselect_all_btn"))
        self.deselect_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2238;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2a2f4c; color: #ffffff; }
        """)
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        toolbar_layout.addWidget(self.deselect_all_btn)

        toolbar_layout.addStretch()

        # Search field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("updates.search_placeholder"))
        self.search_input.setFixedWidth(280)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #161824;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 7px 12px;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #6366f1; }
        """)
        self.search_input.textChanged.connect(self._apply_filter)
        toolbar_layout.addWidget(self.search_input)

        layout.addLayout(toolbar_layout)

        # 3. Mods Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self._set_table_headers()
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        # Table Styling
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #11131e;
                alternate-background-color: #151827;
                border: 1px solid #232738;
                border-radius: 10px;
                outline: none;
            }
            QTableWidget::item {
                border-bottom: 1px solid #1e2235;
            }
            QTableWidget::item:selected {
                background-color: #1e2338;
            }
            QHeaderView::section {
                background-color: #181b2a;
                color: #94a3b8;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.5px;
                padding: 10px 14px;
                border: none;
                border-bottom: 2px solid #282e44;
            }
        """)

        header = self.table.horizontalHeader()
        header.setFixedHeight(46)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 48)

        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 170)

        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 170)

        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 180)

        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 160)

        self.table.verticalHeader().setDefaultSectionSize(self.ROW_HEIGHT)

        layout.addWidget(self.table)

        self.refresh_updates()

    def _update_counter_label(self):
        if self._updatable_count > 0:
            self.counter_label.setText(
                tr("updates.count_available", count=self._updatable_count, total=self._total_installed)
            )
        elif self._total_installed > 0:
            self.counter_label.setText(tr("updates.all_up_to_date", total=self._total_installed))
        else:
            self.counter_label.setText(tr("updates.up_to_date_title"))

    def refresh_updates(self):
        """Loads all installed mods and evaluates updates via API /api/updates."""
        try:
            res = self.api_client.get_updates()
            self.all_mods = res.get("items", [])
            self._updatable_count = res.get("count", 0)
            self._total_installed = res.get("total_installed", len(self.all_mods))

            self._update_counter_label()

            self.update_all_btn.setEnabled(self._updatable_count > 0)
            self._render_table()

        except Exception as e:
            logger.error(f"Erreur API lors de la vérification des mises à jour: {e}")
            self.counter_label.setText(tr("updates.check_error"))

    def _render_table(self):
        """Populates the table with all installed mods in a clear, spacious layout."""
        query = self.search_input.text().lower().strip()
        filtered = [
            item for item in self.all_mods
            if not query or query in item.get("title", "").lower() or query in item.get("source", "").lower()
        ]

        self.table.setRowCount(len(filtered))
        self.checkbox_items.clear()

        for row, item in enumerate(filtered):
            self.table.setRowHeight(row, self.ROW_HEIGHT)
            inst_id = item["installed_id"]
            title = item.get("title", "")
            has_update = item.get("has_update", False)
            source = item.get("source", "manual")
            folder_name = item.get("folder_name", "")

            # 0. Selection Checkbox
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb = QCheckBox()
            cb.setStyleSheet("""
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border-radius: 4px;
                    border: 1px solid #475569;
                    background-color: #1e2238;
                }
                QCheckBox::indicator:hover {
                    border-color: #818cf8;
                }
                QCheckBox::indicator:checked {
                    background-color: #6366f1;
                    border-color: #818cf8;
                }
            """)
            cb.setChecked(has_update)  # Pre-check mods requiring update
            cb.toggled.connect(self._on_selection_changed)
            cb_layout.addWidget(cb)
            self.table.setCellWidget(row, 0, cb_widget)
            self.checkbox_items.append((inst_id, title, cb, has_update))

            # 1. Mod Title + Source Badge + Folder
            title_widget = QWidget()
            t_layout = QVBoxLayout(title_widget)
            t_layout.setContentsMargins(12, 10, 12, 10)
            t_layout.setSpacing(4)
            t_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            title_label = QLabel(title)
            title_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
            title_label.setToolTip(title)
            t_layout.addWidget(title_label)

            sub_layout = QHBoxLayout()
            sub_layout.setContentsMargins(0, 0, 0, 0)
            sub_layout.setSpacing(8)

            src_badge = StatusBadge(source.capitalize(), badge_type=source)
            sub_layout.addWidget(src_badge)

            if folder_name:
                folder_label = QLabel(f"📁 {folder_name}")
                folder_label.setStyleSheet("font-size: 11px; color: #64748b;")
                sub_layout.addWidget(folder_label)

            sub_layout.addStretch()
            t_layout.addLayout(sub_layout)
            self.table.setCellWidget(row, 1, title_widget)

            # 2. Version Actuelle (Pill)
            cur_widget = QWidget()
            c_layout = QHBoxLayout(cur_widget)
            c_layout.setContentsMargins(8, 0, 8, 0)
            c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            cur_ver = item.get("current_version") or "Inconnue"
            cur_lbl = QLabel(cur_ver)
            cur_lbl.setStyleSheet("""
                background-color: #1a1d2e;
                color: #cbd5e1;
                border: 1px solid #2e344d;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            """)
            c_layout.addWidget(cur_lbl)
            self.table.setCellWidget(row, 2, cur_widget)

            # 3. Nouvelle Version (Pill)
            new_widget = QWidget()
            n_layout = QHBoxLayout(new_widget)
            n_layout.setContentsMargins(8, 0, 8, 0)
            n_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            new_ver = item.get("new_version") or "-"
            new_lbl = QLabel(f"▲ {new_ver}" if has_update else new_ver)
            if has_update:
                new_lbl.setStyleSheet("""
                    background-color: #064e3b;
                    color: #34d399;
                    border: 1px solid #059669;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 700;
                """)
            else:
                new_lbl.setStyleSheet("""
                    background-color: #1a1d2e;
                    color: #64748b;
                    border: 1px solid #2e344d;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 500;
                """)
            n_layout.addWidget(new_lbl)
            self.table.setCellWidget(row, 3, new_widget)

            # 4. Statut (StatusBadge)
            stat_widget = QWidget()
            s_layout = QHBoxLayout(stat_widget)
            s_layout.setContentsMargins(8, 0, 8, 0)
            s_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if has_update:
                badge = StatusBadge(tr("updates.badge_update_avail"), badge_type="warning")
            elif item.get("catalog_mod_id") or item.get("remote_id"):
                badge = StatusBadge(tr("updates.badge_up_to_date"), badge_type="active")
            else:
                badge = StatusBadge(tr("updates.badge_local"), badge_type="info")
            s_layout.addWidget(badge)
            self.table.setCellWidget(row, 4, stat_widget)

            # 5. Action Button
            action_widget = QWidget()
            act_layout = QHBoxLayout(action_widget)
            act_layout.setContentsMargins(8, 0, 8, 0)
            act_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            if has_update:
                up_btn = QPushButton(tr("updates.btn_update_single"))
                up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                up_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #6366f1;
                        color: #ffffff;
                        font-weight: 700;
                        font-size: 12px;
                        border-radius: 6px;
                        padding: 7px 14px;
                        min-height: 20px;
                    }
                    QPushButton:hover { background-color: #4f46e5; }
                """)
                up_btn.clicked.connect(lambda _, mid=inst_id, t=title: self.update_single_mod(mid, t))
                act_layout.addWidget(up_btn)
            else:
                up_to_date_btn = QPushButton(tr("updates.btn_up_to_date"))
                up_to_date_btn.setEnabled(False)
                up_to_date_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #181b29;
                        color: #475569;
                        font-weight: 600;
                        font-size: 12px;
                        border-radius: 6px;
                        padding: 7px 14px;
                        border: 1px solid #232738;
                        min-height: 20px;
                    }
                """)
                act_layout.addWidget(up_to_date_btn)

            self.table.setCellWidget(row, 5, action_widget)

        self._on_selection_changed()

    def _apply_filter(self):
        self._render_table()

    def _on_selection_changed(self):
        """Updates the batch button label and state based on selected checked mods."""
        selected_updatable = [mid for mid, _, cb, has_up in self.checkbox_items if cb.isChecked() and has_up]
        total_selected = [mid for mid, _, cb, _ in self.checkbox_items if cb.isChecked()]

        count = len(selected_updatable)
        if count > 0:
            self.update_selected_btn.setText(tr("updates.update_selected_batch", count=count))
            self.update_selected_btn.setEnabled(True)
        elif len(total_selected) > 0:
            self.update_selected_btn.setText(tr("updates.reinstall_selected_batch", count=len(total_selected)))
            self.update_selected_btn.setEnabled(True)
        else:
            self.update_selected_btn.setText(tr("updates.update_selected_batch", count=0))
            self.update_selected_btn.setEnabled(False)

    def select_all(self):
        for _, _, cb, _ in self.checkbox_items:
            cb.setChecked(True)

    def deselect_all(self):
        for _, _, cb, _ in self.checkbox_items:
            cb.setChecked(False)

    def select_updates_only(self):
        for _, _, cb, has_update in self.checkbox_items:
            cb.setChecked(has_update)

    def update_single_mod(self, installed_id: int, title: str):
        self.progress_dlg = ProgressDialog(tr("updates.update_progress", name=title), self)
        self.progress_dlg.set_status(tr("updates.update_single_progress"))
        self.progress_dlg.set_indeterminate(True)
        self.progress_dlg.show()

        self.worker = UpdateWorker(mode="single", installed_id=installed_id)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def update_selected_mods(self):
        selected_updatable = [mid for mid, _, cb, has_up in self.checkbox_items if cb.isChecked() and has_up]
        selected_all = [mid for mid, _, cb, _ in self.checkbox_items if cb.isChecked()]

        target_ids = selected_updatable if selected_updatable else selected_all
        if not target_ids:
            QMessageBox.information(self, tr("dialogs.info_title"), tr("updates.select_at_least_one"))
            return

        count = len(target_ids)
        msg = tr("updates.batch_confirm_msg", count=count)
        reply = QMessageBox.question(
            self,
            tr("updates.batch_confirm_title"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.progress_dlg = ProgressDialog(tr("updates.batch_progress_title"), self)
            self.progress_dlg.set_status(tr("updates.batch_progress_status", count=count))
            self.progress_dlg.set_indeterminate(True)
            self.progress_dlg.show()

            self.worker = UpdateWorker(mode="batch", installed_ids=target_ids)
            self.worker.finished.connect(self._on_finished)
            self.worker.start()

    def update_all_mods(self):
        updatable_mods = [item for item in self.all_mods if item.get("has_update")]
        if not updatable_mods:
            QMessageBox.information(self, tr("updates.all_confirm_title"), tr("updates.already_up_to_date_msg"))
            return

        count = len(updatable_mods)
        reply = QMessageBox.question(
            self,
            tr("updates.all_confirm_title"),
            tr("updates.all_confirm_msg", count=count),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.progress_dlg = ProgressDialog(tr("updates.all_progress_title"), self)
            self.progress_dlg.set_status(tr("updates.batch_progress_status", count=count))
            self.progress_dlg.set_indeterminate(True)
            self.progress_dlg.show()

            self.worker = UpdateWorker(mode="all")
            self.worker.finished.connect(self._on_finished)
            self.worker.start()

    def _on_finished(self, success: bool, msg: str):
        if hasattr(self, "progress_dlg") and self.progress_dlg:
            self.progress_dlg.close()
        if success:
            QMessageBox.information(self, tr("updates.update_success_title"), msg)
            self.updates_applied.emit()
        else:
            QMessageBox.warning(self, tr("updates.update_error_title"), msg)
        self.refresh_updates()

    def _set_table_headers(self):
        self.table.setHorizontalHeaderLabels(
            [
                "☑",
                tr("updates.col_name"),
                tr("updates.col_current"),
                tr("updates.col_new"),
                tr("updates.col_source"),
                tr("updates.col_actions"),
            ]
        )

    def retranslate_ui(self):
        """Retranslates all text elements in UpdatesView."""
        self.main_title.setText(tr("updates.title"))
        self.refresh_btn.setText(tr("updates.refresh_btn"))
        self.update_all_btn.setText(tr("updates.update_all_btn"))
        self.select_updates_btn.setText(tr("updates.select_updates_btn"))
        self.select_updates_btn.setToolTip(tr("updates.select_updates_tip"))
        self.select_all_btn.setText(tr("updates.select_all_btn"))
        self.deselect_all_btn.setText(tr("updates.deselect_all_btn"))
        self.search_input.setPlaceholderText(tr("updates.search_placeholder"))
        self._set_table_headers()
        self._on_selection_changed()
        self._update_counter_label()
        self._render_table()
