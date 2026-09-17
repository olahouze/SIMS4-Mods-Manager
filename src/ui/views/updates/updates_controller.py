"""
UpdatesActionController: Orchestrates update confirmations, progress dialogs, and UpdateWorker threads.
"""
from typing import List, Dict, Any, Callable, Optional
from PySide6.QtWidgets import QWidget, QMessageBox

from src.ui.components.progress_dialog import ProgressDialog
from src.ui.workers.update_workers import UpdateWorker
from src.i18n import tr


class UpdatesActionController:
    """Handles confirmation dialogs, progress modal setup, and QThread worker invocation for updates."""

    def __init__(self, parent_widget: QWidget):
        self.parent = parent_widget
        self.worker: Optional[UpdateWorker] = None
        self.progress_dlg: Optional[ProgressDialog] = None

    def update_single_mod(self, installed_id: int, title: str, on_finished_callback: Callable[[bool, str], None]):
        self.progress_dlg = ProgressDialog(tr("updates.update_progress", name=title), self.parent)
        self.progress_dlg.set_status(tr("updates.update_single_progress"))
        self.progress_dlg.set_indeterminate(True)
        self.progress_dlg.show()

        self.worker = UpdateWorker(mode="single", installed_id=installed_id, parent=self.parent)
        self.worker.finished.connect(lambda s, m: self._handle_worker_finish(s, m, on_finished_callback))
        self.worker.start()

    def update_selected_mods(self, target_ids: List[int], on_finished_callback: Callable[[bool, str], None]):
        if not target_ids:
            QMessageBox.information(self.parent, tr("dialogs.info_title"), tr("updates.select_at_least_one"))
            return

        count = len(target_ids)
        msg = tr("updates.batch_confirm_msg", count=count)
        reply = QMessageBox.question(
            self.parent,
            tr("updates.batch_confirm_title"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.progress_dlg = ProgressDialog(tr("updates.batch_progress_title"), self.parent)
            self.progress_dlg.set_status(tr("updates.batch_progress_status", count=count))
            self.progress_dlg.set_indeterminate(True)
            self.progress_dlg.show()

            self.worker = UpdateWorker(mode="batch", installed_ids=target_ids, parent=self.parent)
            self.worker.finished.connect(lambda s, m: self._handle_worker_finish(s, m, on_finished_callback))
            self.worker.start()

    def update_all_mods(self, all_mods: List[Dict[str, Any]], on_finished_callback: Callable[[bool, str], None]):
        updatable_mods = [item for item in all_mods if item.get("has_update")]
        if not updatable_mods:
            QMessageBox.information(self.parent, tr("updates.all_confirm_title"), tr("updates.already_up_to_date_msg"))
            return

        count = len(updatable_mods)
        reply = QMessageBox.question(
            self.parent,
            tr("updates.all_confirm_title"),
            tr("updates.all_confirm_msg", count=count),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.progress_dlg = ProgressDialog(tr("updates.all_progress_title"), self.parent)
            self.progress_dlg.set_status(tr("updates.batch_progress_status", count=count))
            self.progress_dlg.set_indeterminate(True)
            self.progress_dlg.show()

            self.worker = UpdateWorker(mode="all", parent=self.parent)
            self.worker.finished.connect(lambda s, m: self._handle_worker_finish(s, m, on_finished_callback))
            self.worker.start()

    def _handle_worker_finish(self, success: bool, msg: str, on_finished_callback: Callable[[bool, str], None]):
        if self.progress_dlg:
            self.progress_dlg.close()
            self.progress_dlg = None
        on_finished_callback(success, msg)
