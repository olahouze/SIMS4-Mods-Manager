"""
ModDetailView: Orchestrator view for displaying full mod details,
composed of specialized sub-components in src/ui/views/mod_detail/.
"""

from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QProgressBar,
)
from PySide6.QtCore import Signal

from src.api.client import get_api_client
from src.ui.workers import FetchDetailsWorker
from src.ui.views.mod_detail import (
    DetailHeaderWidget,
    DetailRequirementsWidget,
    DetailGalleryWidget,
    DetailDescriptionWidget,
    ModDetailCompatMixin,
)
from src.i18n import tr
from src.utils.logger import logger
from src.utils.thread_utils import safe_stop_thread


class ModDetailView(QWidget, ModDetailCompatMixin):
    """
    Dedicated full-page view taking 100% of the application screen
    to display rich mod details, requirements, dependencies, and actions.
    Accessible from both 'Catalogue' and 'Mes Mods'.
    """

    back_requested = Signal()
    install_requested = Signal(dict)
    uninstall_requested = Signal(dict)
    open_folder_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.mod_data: Dict[str, Any] = {}
        self.origin_name: str = "Catalogue"
        self.origin_index: int = 1
        self._current_load_id: int = 0
        self.worker: Optional[FetchDetailsWorker] = None

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.main_scroll = QScrollArea(self)
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setStyleSheet("QScrollArea { border: none; background-color: #060911; }")

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: #060911;")
        self.c_layout = QVBoxLayout(self.content_widget)
        self.c_layout.setContentsMargins(28, 20, 28, 30)
        self.c_layout.setSpacing(14)

        # 1. Header & Hero Card
        self.header_widget = DetailHeaderWidget(self.content_widget)
        self.header_widget.back_requested.connect(self.back_requested.emit)
        self.header_widget.install_requested.connect(lambda: self.install_requested.emit(self.mod_data))
        self.header_widget.uninstall_requested.connect(lambda: self.uninstall_requested.emit(self.mod_data))
        self.header_widget.open_folder_requested.connect(
            lambda: self.open_folder_requested.emit(self.mod_data.get("folder_name", ""))
        )
        self.header_widget.open_web_requested.connect(self._on_web_clicked)
        self.c_layout.addWidget(self.header_widget)

        # 2. Requirements & Dependencies Section
        self.requirements_widget = DetailRequirementsWidget(self.content_widget)
        self.requirements_widget.toggle_comment_requested.connect(self._on_toggle_comment)
        self.requirements_widget.override_changed.connect(self._on_override_changed)
        self.c_layout.addWidget(self.requirements_widget)

        # 3. Screenshot Gallery Section
        self.gallery_widget = DetailGalleryWidget(self.content_widget)
        self.c_layout.addWidget(self.gallery_widget)

        # 4. Loading Bar
        self.loading_bar = QProgressBar(self.content_widget)
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setFixedHeight(6)
        self.loading_bar.setStyleSheet("""
            QProgressBar { background-color: #1e293b; border-radius: 3px; }
            QProgressBar::chunk { background-color: #6366f1; border-radius: 3px; }
        """)
        self.c_layout.addWidget(self.loading_bar)

        # 5. HTML Description Section
        self.desc_widget = DetailDescriptionWidget(self.content_widget)
        self.c_layout.addWidget(self.desc_widget, stretch=1)

        self.main_scroll.setWidget(self.content_widget)
        main_layout.addWidget(self.main_scroll, stretch=1)

    # Compatibility properties are inherited from ModDetailCompatMixin

    # ----------------- Core Operations -----------------
    def load_mod(self, mod_data: dict, origin_name: str = "Catalogue", origin_index: int = 1):
        """Loads and displays mod details, initiating background fetch for rich content."""
        self._current_load_id += 1
        current_load_id = self._current_load_id

        self.mod_data = mod_data
        self.origin_name = origin_name
        self.origin_index = origin_index

        self.main_scroll.verticalScrollBar().setValue(0)
        self.header_widget.update_mod_info(mod_data, origin_name, origin_index)
        self.desc_widget.set_loading()
        self.gallery_widget.clear_gallery()

        # Render requirements or show loading skeleton
        if mod_data.get("requirements_status") == "RESOLVED" and mod_data.get("dependencies"):
            self._render_requirements(mod_data)
        else:
            self._set_requirements_loading()

        # Stop previous background detail fetcher cleanly
        if self.worker:
            safe_stop_thread(self.worker)
            self.worker = None

        self.loading_bar.setVisible(True)

        # Background worker for remote details
        self.worker = FetchDetailsWorker(
            mod_id=mod_data.get("id") or mod_data.get("catalog_mod_id"),
            page_url=mod_data.get("page_url"),
            source=mod_data.get("source", "loverslab"),
            remote_id=str(mod_data.get("remote_id", "")),
            load_id=current_load_id,
        )
        self.worker.finished.connect(lambda data, lid=current_load_id: self._on_details_fetched(data, lid))
        self.worker.failed.connect(lambda err, lid=current_load_id: self._on_details_failed(err, lid))
        self.worker.start()

    def _set_requirements_loading(self):
        """Displays the loading skeleton for requirements and dependencies."""
        self.requirements_widget.set_loading()

    def _render_requirements(self, data: dict):
        res = self.requirements_widget.render_requirements(data)
        if not self.header_widget.is_installed:
            unfound = res.get("unfound", [])
            to_install = res.get("to_install", [])
            if unfound:
                self.header_widget.install_btn.setText("⚠️ Installation Partielle")
            elif to_install:
                self.header_widget.install_btn.setText("📥 Installer (+ Dépendances)")
            else:
                self.header_widget.install_btn.setText(tr("mod_detail.btn_install"))

        if res.get("unfound") or res.get("comments"):
            self._trigger_check_report_status(data)

    def _trigger_check_report_status(self, data: dict):
        self.requirements_widget._trigger_check_report_status(data)

    def _on_report_status_ready(self, res: dict):
        self.requirements_widget._on_report_status_ready(res)

    def _on_report_sent_success(self, reported_at: str):
        self.requirements_widget._on_report_sent_success(reported_at)

    def _on_details_fetched(self, full_details: dict, load_id: Optional[int] = None):
        if load_id is not None and load_id != self._current_load_id:
            logger.debug(f"Ignoring obsolete details fetched for load_id={load_id} (current={self._current_load_id})")
            return

        self.loading_bar.setVisible(False)
        self.mod_data.update(full_details)
        self._render_requirements(full_details)
        self.gallery_widget.render_gallery(full_details.get("screenshots", []), self._current_load_id)
        self.desc_widget.set_content(full_details.get("description", ""))

    def _on_details_failed(self, err_msg: str, load_id: Optional[int] = None):
        if load_id is not None and load_id != self._current_load_id:
            return

        self.loading_bar.setVisible(False)
        logger.debug(f"Details fetch error in ModDetailView: {err_msg}")
        self.desc_widget.set_error(err_msg)
        if "Analyse des dépendances" in self.req_title.text():
            self.req_frame.setVisible(False)

    def _on_toggle_comment(self, dep: dict, to_comment: bool):
        title = dep.get("title") or ""
        if "requirements_overrides" not in self.mod_data or not isinstance(
            self.mod_data["requirements_overrides"], dict
        ):
            self.mod_data["requirements_overrides"] = {}
        self.mod_data["requirements_overrides"][title] = "COMMENT" if to_comment else "MOD"
        dep["is_comment"] = to_comment

        cat_id = self.mod_data.get("id") or self.mod_data.get("catalog_mod_id")
        if cat_id:
            from src.ui.workers.generic_runnable import run_async_ui_task

            def _async_save():
                try:
                    client = get_api_client()
                    client.save_requirements_override(
                        {
                            "catalog_mod_id": cat_id,
                            "overrides": {title: "COMMENT" if to_comment else "MOD"},
                        }
                    )
                except Exception as e:
                    logger.debug(f"Erreur enregistrement override dans ModDetailView: {e}")

            run_async_ui_task(_async_save)

        self._render_requirements(self.mod_data)

    def _on_override_changed(self, module_title: str, override_type: str):
        if not module_title:
            return
        if "requirements_overrides" not in self.mod_data or not isinstance(
            self.mod_data["requirements_overrides"], dict
        ):
            self.mod_data["requirements_overrides"] = {}
        self.mod_data["requirements_overrides"][module_title] = override_type

        for dep in self.mod_data.get("dependencies", []):
            t = (dep.get("title") or f"Mod #{dep.get('remote_id')}").strip()
            if t == module_title.strip():
                dep["is_comment"] = override_type == "COMMENT"

        cat_id = self.mod_data.get("id") or self.mod_data.get("catalog_mod_id")
        if cat_id:
            from src.ui.workers.generic_runnable import run_async_ui_task

            def _async_save():
                try:
                    client = get_api_client()
                    client.save_requirements_override(
                        {
                            "catalog_mod_id": cat_id,
                            "overrides": {module_title: override_type},
                        }
                    )
                except Exception as e:
                    logger.debug(f"Erreur sync override dans ModDetailView: {e}")

            run_async_ui_task(_async_save)

        self._render_requirements(self.mod_data)

    def _on_web_clicked(self):
        import webbrowser

        url = self.mod_data.get("page_url", "")
        if url:
            webbrowser.open(url)

    def retranslate_ui(self):
        """Retranslates all sub-components in ModDetailView."""
        self.header_widget.retranslate_ui()
        self.gallery_widget.retranslate_ui()

    def cleanup(self):
        """Exécute l'opération cleanup."""
        if self.worker:
            safe_stop_thread(self.worker)
            self.worker = None
        self.gallery_widget.cleanup()
        self.desc_widget.stop_worker()

    def closeEvent(self, event):
        """Exécute l'opération closeevent.

        Args:
            event: Paramètre event.
        """
        self.cleanup()
        super().closeEvent(event)
