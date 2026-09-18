"""
DownloadsView: Dedicated background download and installation manager.
Allows concurrent or queued mod installations while users freely navigate the catalog.
"""
from typing import Dict, Any
import os
import subprocess
import sys
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QFrame,
    QMessageBox,
)

from src.i18n import tr
from src.ui.workers.catalog_workers import InstallWorker
from src.utils.logger import logger
from src.core.config import AppConfig


class DownloadCardWidget(QFrame):
    """Card widget representing an individual background download and installation task."""

    cancelled = Signal(str)  # task_id
    retry_requested = Signal(dict)  # mod_data
    details_requested = Signal(dict)  # mod_data
    open_folder_requested = Signal(str)  # folder_name or path

    def __init__(self, task_id: str, mod_data: dict, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.mod_data = mod_data
        self.status = "waiting"  # "waiting", "downloading", "extracting", "completed", "failed", "cancelled"
        self.progress_val = 0
        self.details_text = tr("downloads.status_waiting")
        self.error_msg = ""
        self.init_ui()

    def init_ui(self):
        self.setObjectName("DownloadCard")
        self.setStyleSheet("""
            QFrame#DownloadCard {
                background-color: #161b2a;
                border: 1px solid #232b42;
                border-radius: 12px;
                padding: 14px;
            }
            QFrame#DownloadCard:hover {
                border-color: #38bdf8;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # 1. Top row: Source badge, Title, Status badge, and Actions
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        source = (self.mod_data.get("source") or "loverslab").upper()
        source_color = "#3b82f6" if source == "LOVERSLAB" else "#f97316"
        self.source_badge = QLabel(source)
        self.source_badge.setStyleSheet(f"""
            background-color: rgba(30, 41, 59, 0.8);
            color: {source_color};
            border: 1px solid {source_color};
            border-radius: 6px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 700;
        """)
        top_row.addWidget(self.source_badge)

        self.title_label = QLabel(self.mod_data.get("title") or "Mod sans titre")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #f8fafc;")
        top_row.addWidget(self.title_label, stretch=1)

        # Status Badge Pill
        self.status_badge = QLabel(tr("downloads.status_waiting"))
        self._update_status_badge_style("waiting")
        top_row.addWidget(self.status_badge)

        # Action Buttons
        self.btn_details = QPushButton(tr("downloads.btn_view_details"))
        self.btn_details.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #334155; color: #f8fafc; }
        """)
        self.btn_details.clicked.connect(lambda: self.details_requested.emit(self.mod_data))
        top_row.addWidget(self.btn_details)

        self.btn_open_folder = QPushButton(tr("downloads.btn_open_folder"))
        self.btn_open_folder.setStyleSheet("""
            QPushButton {
                background-color: #065f46;
                color: #34d399;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #047857; color: #ffffff; }
        """)
        self.btn_open_folder.setVisible(False)
        self.btn_open_folder.clicked.connect(self._on_open_folder)
        top_row.addWidget(self.btn_open_folder)

        self.btn_retry = QPushButton(tr("downloads.btn_retry"))
        self.btn_retry.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d;
                color: #fca5a5;
                border: 1px solid #dc2626;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #991b1b; color: #ffffff; }
        """)
        self.btn_retry.setVisible(False)
        self.btn_retry.clicked.connect(lambda: self.retry_requested.emit(self.mod_data))
        top_row.addWidget(self.btn_retry)

        self.btn_cancel = QPushButton(tr("downloads.btn_cancel"))
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #f87171;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #334155; color: #ef4444; }
        """)
        self.btn_cancel.clicked.connect(lambda: self.cancelled.emit(self.task_id))
        top_row.addWidget(self.btn_cancel)

        layout.addLayout(top_row)

        # 2. Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0b0f19;
                border: 1px solid #1e293b;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 3. Bottom Row: Details / Speed / Percent
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.details_label = QLabel(self.details_text)
        self.details_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
        bottom_row.addWidget(self.details_label, stretch=1)

        self.percent_label = QLabel("0%")
        self.percent_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #38bdf8;")
        bottom_row.addWidget(self.percent_label)

        layout.addLayout(bottom_row)

    def _update_status_badge_style(self, status: str):
        if status in ["downloading", "extracting"]:
            self.status_badge.setText(
                tr("downloads.status_downloading") if status == "downloading" else tr("downloads.status_extracting")
            )
            self.status_badge.setStyleSheet("""
                background-color: rgba(14, 165, 233, 0.15);
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            """)
        elif status == "completed":
            self.status_badge.setText(tr("downloads.status_completed"))
            self.status_badge.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.15);
                color: #34d399;
                border: 1px solid #10b981;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            """)
        elif status == "failed":
            self.status_badge.setText(tr("downloads.status_failed"))
            self.status_badge.setStyleSheet("""
                background-color: rgba(239, 68, 68, 0.15);
                color: #f87171;
                border: 1px solid #ef4444;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            """)
        elif status == "cancelled":
            self.status_badge.setText("Annulé")
            self.status_badge.setStyleSheet("""
                background-color: rgba(148, 163, 184, 0.15);
                color: #94a3b8;
                border: 1px solid #64748b;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            """)
        else:
            self.status_badge.setText(tr("downloads.status_waiting"))
            self.status_badge.setStyleSheet("""
                background-color: rgba(51, 65, 85, 0.5);
                color: #94a3b8;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            """)

    def update_progress(self, percent: int, status_text: str, details: str = ""):
        self.progress_val = percent
        self.progress_bar.setValue(percent)
        self.percent_label.setText(f"{percent}%")

        if percent >= 75:
            self.status = "extracting"
        else:
            self.status = "downloading"
        self._update_status_badge_style(self.status)

        det = f"{status_text} - {details}" if details else status_text
        self.details_label.setText(det)

    def mark_completed(self, message: str = ""):
        self.status = "completed"
        self.progress_val = 100
        self.progress_bar.setValue(100)
        self.percent_label.setText("100%")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0b0f19;
                border: 1px solid #1e293b;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: #10b981;
                border-radius: 3px;
            }
        """)
        self._update_status_badge_style("completed")
        self.details_label.setText(message or tr("downloads.status_completed"))
        self.btn_cancel.setVisible(False)
        self.btn_open_folder.setVisible(True)
        self.btn_retry.setVisible(False)

    def mark_failed(self, error: str):
        self.status = "failed"
        self.error_msg = error
        self._update_status_badge_style("failed")
        self.details_label.setText(error or tr("downloads.status_failed"))
        self.details_label.setStyleSheet("font-size: 12px; color: #f87171;")
        self.btn_cancel.setVisible(False)
        self.btn_retry.setVisible(True)
        self.btn_open_folder.setVisible(False)

    def mark_cancelled(self):
        self.status = "cancelled"
        self._update_status_badge_style("cancelled")
        self.details_label.setText("Téléchargement annulé par l'utilisateur.")
        self.btn_cancel.setVisible(False)
        self.btn_retry.setVisible(True)
        self.btn_open_folder.setVisible(False)

    def _on_open_folder(self):
        folder_name = self.mod_data.get("folder_name") or self.mod_data.get("title") or ""
        self.open_folder_requested.emit(folder_name)


class DownloadsView(QWidget):
    """
    Spacious, dedicated Downloads view allowing users to track real-time
    downloads and installations while browsing the catalog concurrently.
    """

    active_count_changed = Signal(int)
    install_finished = Signal(bool, str)
    details_requested = Signal(dict)
    open_folder_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.card_widgets: Dict[str, DownloadCardWidget] = {}
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # 1. Header Toolbar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_label = QLabel(tr("downloads.title"))
        self.title_label.setStyleSheet("font-size: 20px; font-weight: 800; color: #f8fafc;")
        title_col.addWidget(self.title_label)

        self.subtitle_label = QLabel(tr("downloads.subtitle"))
        self.subtitle_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
        title_col.addWidget(self.subtitle_label)
        header_layout.addLayout(title_col, stretch=1)

        # Summary Pills
        self.active_pill = QLabel(tr("downloads.active_count", count=0))
        self.active_pill.setStyleSheet("""
            background-color: rgba(14, 165, 233, 0.15);
            color: #38bdf8;
            border: 1px solid #0284c7;
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: 700;
        """)
        header_layout.addWidget(self.active_pill)

        self.completed_pill = QLabel(tr("downloads.completed_count", count=0))
        self.completed_pill.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid #10b981;
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: 700;
        """)
        header_layout.addWidget(self.completed_pill)

        self.btn_clear_history = QPushButton(tr("downloads.clear_history"))
        self.btn_clear_history.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #334155; color: #ffffff; }
        """)
        self.btn_clear_history.clicked.connect(self.clear_finished_downloads)
        header_layout.addWidget(self.btn_clear_history)

        self.btn_open_mods = QPushButton(tr("downloads.open_mods_folder"))
        self.btn_open_mods.setStyleSheet("""
            QPushButton {
                background-color: #0f766e;
                color: #ffffff;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #115e59; }
        """)
        self.btn_open_mods.clicked.connect(self.open_mods_directory)
        header_layout.addWidget(self.btn_open_mods)

        main_layout.addLayout(header_layout)

        # 2. Scroll Area for Download Cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        self.scroll_content = QWidget()
        self.cards_layout = QVBoxLayout(self.scroll_content)
        self.cards_layout.setContentsMargins(0, 4, 8, 4)
        self.cards_layout.setSpacing(12)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Empty State Placeholder
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setContentsMargins(20, 60, 20, 40)
        empty_layout.setSpacing(12)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_icon = QLabel("📥")
        empty_icon.setStyleSheet("font-size: 48px;")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)

        empty_title = QLabel(tr("downloads.empty_title"))
        empty_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #94a3b8;")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)

        empty_subtitle = QLabel(tr("downloads.empty_subtitle"))
        empty_subtitle.setStyleSheet("font-size: 13px; color: #64748b;")
        empty_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_subtitle)

        self.cards_layout.addWidget(self.empty_widget)
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

    def start_download(self, mod_data: dict) -> str:
        """Starts a background download task for the given mod."""
        mod_id = str(mod_data.get("id") or mod_data.get("remote_id") or mod_data.get("title"))
        task_id = f"{mod_id}_{len(self.tasks) + 1}"

        self.empty_widget.setVisible(False)

        card = DownloadCardWidget(task_id, mod_data, parent=self.scroll_content)
        card.cancelled.connect(self._on_cancel_task)
        card.retry_requested.connect(self.start_download)
        card.details_requested.connect(self.details_requested.emit)
        card.open_folder_requested.connect(self.open_mod_folder)

        # Insert at the top
        self.cards_layout.insertWidget(0, card)
        self.card_widgets[task_id] = card

        worker = InstallWorker(mod_data)
        worker.progress.connect(lambda p, s, d, tid=task_id: self._on_worker_progress(tid, p, s, d))
        worker.finished.connect(lambda ok, msg, tid=task_id: self._on_worker_finished(tid, ok, msg))

        self.tasks[task_id] = {
            "mod_data": mod_data,
            "worker": worker,
            "status": "downloading",
        }

        worker.start()
        self._update_counters()
        return task_id

    def _on_worker_progress(self, task_id: str, percent: int, status: str, details: str):
        card = self.card_widgets.get(task_id)
        if card:
            card.update_progress(percent, status, details)

    def _on_worker_finished(self, task_id: str, success: bool, message: str):
        task_info = self.tasks.get(task_id)
        if task_info:
            task_info["status"] = "completed" if success else "failed"

        card = self.card_widgets.get(task_id)
        if card:
            if success:
                card.mark_completed(message)
            else:
                card.mark_failed(message)

        self._update_counters()
        self.install_finished.emit(success, message)

    def _on_cancel_task(self, task_id: str):
        task_info = self.tasks.get(task_id)
        if task_info and task_info.get("worker"):
            worker: InstallWorker = task_info["worker"]
            worker.cancel()
            task_info["status"] = "cancelled"

        card = self.card_widgets.get(task_id)
        if card:
            card.mark_cancelled()

        self._update_counters()

    def _update_counters(self):
        active = sum(1 for t in self.tasks.values() if t.get("status") in ["waiting", "downloading", "extracting"])
        completed = sum(1 for t in self.tasks.values() if t.get("status") == "completed")

        self.active_pill.setText(tr("downloads.active_count", count=active))
        self.completed_pill.setText(tr("downloads.completed_count", count=completed))

        self.active_count_changed.emit(active)

    def clear_finished_downloads(self):
        """Removes completed, cancelled, or failed cards from view."""
        to_remove = [
            tid for tid, t in self.tasks.items() if t.get("status") in ["completed", "failed", "cancelled"]
        ]
        for tid in to_remove:
            card = self.card_widgets.pop(tid, None)
            if card:
                self.cards_layout.removeWidget(card)
                card.deleteLater()
            self.tasks.pop(tid, None)

        if not self.card_widgets:
            self.empty_widget.setVisible(True)

        self._update_counters()

    def refresh_downloads(self):
        """Called when user opens the Downloads tab."""
        self._update_counters()

    def open_mods_directory(self):
        try:
            config = AppConfig.load()
            mods_dir = config.mods_folder
            if mods_dir and os.path.exists(mods_dir):
                if sys.platform == "win32":
                    os.startfile(mods_dir)
                else:
                    subprocess.Popen(["xdg-open", str(mods_dir)])
            else:
                QMessageBox.warning(self, tr("dialogs.warning_title"), "Le dossier Mods n'a pas été trouvé.")
        except Exception as e:
            logger.error(f"Erreur ouverture dossier mods: {e}")

    def open_mod_folder(self, folder_name: str):
        self.open_folder_requested.emit(folder_name)
        try:
            config = AppConfig.load()
            mods_dir = config.mods_folder
            target = os.path.join(mods_dir, folder_name) if folder_name else mods_dir
            if not os.path.exists(target):
                target = mods_dir
            if os.path.exists(target):
                if sys.platform == "win32":
                    os.startfile(target)
                else:
                    subprocess.Popen(["xdg-open", str(target)])
        except Exception as e:
            logger.error(f"Erreur ouverture dossier du mod: {e}")

    def retranslate_ui(self):
        self.title_label.setText(tr("downloads.title"))
        self.subtitle_label.setText(tr("downloads.subtitle"))
        self.btn_clear_history.setText(tr("downloads.clear_history"))
        self.btn_open_mods.setText(tr("downloads.open_mods_folder"))
        self._update_counters()
