"""
Spacious modern view displaying all installed mods with current and new versions,
individual update buttons, selection checkboxes, and batch update capabilities.
"""

from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QHeaderView,
    QMessageBox,
    QCheckBox,
)
from PySide6.QtCore import Signal

from src.api.client import get_api_client
from src.ui.theme import Theme
from src.ui.workers.update_workers import UpdateWorker
from src.ui.views.updates.updates_row_builder import UpdatesRowBuilder
from src.ui.views.updates.updates_controller import UpdatesActionController
from src.ui.views.updates.updates_toolbar import build_updates_header, build_updates_toolbar
from src.i18n import tr
from src.utils.logger import logger

__all__ = ["UpdatesView", "UpdateWorker"]


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
        self.controller = UpdatesActionController(self)
        self.init_ui()

    @property
    def worker(self) -> Optional[UpdateWorker]:
        """Exécute l'opération worker.

        Returns:
            Résultat de l'opération worker.
        """
        return self.controller.worker

    @property
    def progress_dlg(self):
        """Exécute l'opération progress dlg.

        Returns:
            Résultat de l'opération progress_dlg.
        """
        return self.controller.progress_dlg

    def init_ui(self):
        """Exécute l'opération init ui."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Header Bar: Stats & Main Actions
        layout.addLayout(build_updates_header(self))

        # 2. Controls & Search Toolbar
        layout.addLayout(build_updates_toolbar(self))

        # 3. Mods Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self._set_table_headers()
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(Theme.table_style())

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
        """Exécute l'opération refresh updates."""
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
        query = self.search_input.text().lower().strip()
        filtered = [
            item
            for item in self.all_mods
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

            cb_cell, cb = UpdatesRowBuilder.create_checkbox_cell(
                is_checked=has_update,
                on_toggle=self._on_selection_changed,
            )
            self.table.setCellWidget(row, 0, cb_cell)
            self.checkbox_items.append((inst_id, title, cb, has_update))

            self.table.setCellWidget(row, 1, UpdatesRowBuilder.create_title_cell(title, source, folder_name))
            self.table.setCellWidget(row, 2, UpdatesRowBuilder.create_version_pill(item.get("current_version", "")))
            self.table.setCellWidget(
                row, 3, UpdatesRowBuilder.create_new_version_pill(item.get("new_version", ""), has_update)
            )

            has_link = bool(item.get("catalog_mod_id") or item.get("remote_id"))
            self.table.setCellWidget(row, 4, UpdatesRowBuilder.create_status_cell(has_update, has_link))

            self.table.setCellWidget(
                row,
                5,
                UpdatesRowBuilder.create_action_cell(
                    has_update,
                    lambda i=inst_id, t=title: self.update_single_mod(i, t),
                ),
            )

        self._on_selection_changed()

    def _apply_filter(self):
        self._render_table()

    def _on_selection_changed(self):
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
        """Exécute l'opération select all."""
        for _, _, cb, _ in self.checkbox_items:
            cb.setChecked(True)

    def deselect_all(self):
        """Exécute l'opération deselect all."""
        for _, _, cb, _ in self.checkbox_items:
            cb.setChecked(False)

    def select_updates_only(self):
        """Exécute l'opération select updates only."""
        for _, _, cb, has_update in self.checkbox_items:
            cb.setChecked(has_update)

    def update_single_mod(self, installed_id: int, title: str):
        """Exécute l'opération update single mod.

        Args:
            installed_id: Paramètre installed_id.
            title: Paramètre title.
        """
        self.controller.update_single_mod(installed_id, title, self._on_finished)

    def update_selected_mods(self):
        """Exécute l'opération update selected mods."""
        selected_updatable = [mid for mid, _, cb, has_up in self.checkbox_items if cb.isChecked() and has_up]
        selected_all = [mid for mid, _, cb, _ in self.checkbox_items if cb.isChecked()]
        target_ids = selected_updatable if selected_updatable else selected_all
        self.controller.update_selected_mods(target_ids, self._on_finished)

    def update_all_mods(self):
        """Exécute l'opération update all mods."""
        self.controller.update_all_mods(self.all_mods, self._on_finished)

    def _on_finished(self, success: bool, msg: str):
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
        """Exécute l'opération retranslate ui."""
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
