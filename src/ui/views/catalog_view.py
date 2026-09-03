import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QGridLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal

from src.core.database import DatabaseManager, CatalogMod, InstalledMod, AccountSession
from src.core.session_manager import SessionManager
from src.core.mod_installer import ModInstaller
from src.providers import ProviderRegistry
from src.ui.components.filter_bar import FilterBar
from src.ui.components.mod_card import ModCard
from src.ui.components.progress_dialog import ProgressDialog
from src.utils.logger import logger

class SyncWorker(QThread):
    progress = Signal(str, int)
    finished = Signal(int, str)

    def __init__(self, max_pages: int = 5):
        super().__init__()
        self.max_pages = max_pages

    def run(self):
        db = DatabaseManager.get_instance()
        total_scraped = 0
        providers = ProviderRegistry.list_providers()

        logger.info(f"Démarrage de la synchronisation ({self.max_pages} pages par source)...")

        for prov_idx, provider in enumerate(providers):
            for page in range(1, self.max_pages + 1):
                pct = int(((page - 1 + (prov_idx * self.max_pages)) / (len(providers) * self.max_pages)) * 100)
                msg = f"Synchronisation de {provider.display_name} (Page {page}/{self.max_pages})..."
                self.progress.emit(msg, pct)
                logger.info(msg)

                try:
                    mods = provider.scrape_catalog(page=page)
                    new_on_page = 0
                    with db.get_session() as session:
                        for m_data in mods:
                            existing = session.query(CatalogMod).filter_by(
                                source=m_data["source"],
                                remote_id=m_data["remote_id"]
                            ).first()

                            if not existing:
                                mod_record = CatalogMod(
                                    source=m_data["source"],
                                    remote_id=m_data["remote_id"],
                                    title=m_data["title"],
                                    author=m_data["author"],
                                    category=m_data.get("category", ""),
                                    page_url=m_data["page_url"],
                                    thumbnail_url=m_data.get("thumbnail_url", ""),
                                    published_date=m_data.get("published_date"),
                                    updated_date=m_data.get("updated_date"),
                                )
                                mod_record.set_tags_list(m_data.get("tags", []))
                                session.add(mod_record)
                                total_scraped += 1
                                new_on_page += 1
                            else:
                                existing.title = m_data["title"]
                                existing.author = m_data["author"]
                                existing.thumbnail_url = m_data.get("thumbnail_url", existing.thumbnail_url)
                                existing.updated_date = m_data.get("updated_date", existing.updated_date)
                                existing.set_tags_list(m_data.get("tags", []))
                        session.commit()
                    logger.info(f"Page {page} traitée : {len(mods)} mods analysés ({new_on_page} nouveaux ajouts).")
                except Exception as e:
                    logger.error(f"Erreur lors du scraping de {provider.display_name} page {page}: {e}", exc_info=True)

        logger.info(f"Synchronisation achevée : {total_scraped} nouveaux mods indexés au total.")
        self.finished.emit(total_scraped, "Synchronisation terminée avec succès.")


class InstallWorker(QThread):
    progress = Signal(str, int)
    finished = Signal(bool, str)

    def __init__(self, mod_data: dict):
        super().__init__()
        self.mod_data = mod_data

    def run(self):
        source = self.mod_data.get("source", "loverslab")
        provider = ProviderRegistry.get_provider(source)
        if not provider:
            self.finished.emit(False, f"Fournisseur '{source}' introuvable.")
            return

        self.progress.emit("Récupération des détails et liens de téléchargement...", 20)
        page_url = self.mod_data.get("page_url", "")
        details = provider.get_mod_details(page_url)

        download_urls = details.get("download_urls", [])
        if not download_urls:
            # Check external links
            ext_links = details.get("external_links", [])
            if ext_links:
                self.finished.emit(
                    False,
                    f"Ce mod nécessite un téléchargement sur un site tiers : {', '.join(ext_links[:2])}"
                )
                return
            self.finished.emit(False, "Aucun lien de téléchargement disponible trouvé.")
            return

        dl_info = download_urls[0]
        dl_url = dl_info["url"] if isinstance(dl_info, dict) else dl_info

        self.progress.emit("Téléchargement du fichier de mod...", 50)
        temp_dir = Path(tempfile.gettempdir()) / "sims4_mod_manager_downloads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        filename = f"mod_{self.mod_data.get('remote_id', 'file')}.zip"
        dest_file = temp_dir / filename

        ok, msg = provider.download_mod_file(dl_url, dest_file)
        if not ok:
            logger.error(f"Échec de l'installation pour '{self.mod_data.get('title')}': {msg}")
            self.finished.emit(False, f"Échec du téléchargement : {msg}")
            return

        self.progress.emit("Installation et organisation dans le dossier Sims 4...", 85)
        db = DatabaseManager.get_instance()
        with db.get_session() as session:
            cat_mod = session.query(CatalogMod).filter_by(
                source=self.mod_data.get("source"),
                remote_id=self.mod_data.get("remote_id")
            ).first()

            install_ok, install_msg = ModInstaller.install_mod_from_file(
                file_path=dest_file,
                catalog_mod=cat_mod,
                source=source,
                custom_title=self.mod_data.get("title"),
                version_date=self.mod_data.get("updated_date"),
                version_str=details.get("version_str", "")
            )

        # Cleanup temp
        try:
            dest_file.unlink(missing_ok=True)
        except Exception:
            pass

        if install_ok:
            logger.info(f"Mod '{self.mod_data.get('title')}' installé avec succès : {install_msg}")
        else:
            logger.error(f"Erreur d'installation pour '{self.mod_data.get('title')}': {install_msg}")

        self.finished.emit(install_ok, install_msg)


class CatalogView(QWidget):
    """Unified multi-source mod catalog view with grid layout and search/filter bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Catalogue Unifié des Mods")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title)

        # Filter Bar
        self.filter_bar = FilterBar()
        self.filter_bar.filters_changed.connect(self.refresh_catalog)
        self.filter_bar.sync_requested.connect(self.start_sync)
        layout.addWidget(self.filter_bar)

        # Scroll Area with Card Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll)

        # Load initial data
        self.refresh_catalog()

    def refresh_catalog(self):
        """Clears and re-populates the catalog grid with filtered items from DB."""
        # Clear existing items
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        filter_state = self.filter_bar.get_filter_state()
        db = DatabaseManager.get_instance()

        with db.get_session() as session:
            query = session.query(CatalogMod)

            # Filter by search text
            search = filter_state["search"]
            if search:
                query = query.filter(
                    (CatalogMod.title.ilike(f"%{search}%")) |
                    (CatalogMod.author.ilike(f"%{search}%")) |
                    (CatalogMod.tags.ilike(f"%{search}%"))
                )

            # Filter by source
            src = filter_state["source"]
            if src == "LoversLab":
                query = query.filter(CatalogMod.source == "loverslab")
            elif src == "Patreon":
                query = query.filter(CatalogMod.source == "patreon")

            # Filter by access
            access = filter_state["access"]
            if "Public" in access:
                query = query.filter(CatalogMod.patreon_status.in_(["PUBLIC", "NONE"]))
            elif "Débloqué" in access:
                query = query.filter(CatalogMod.patreon_status == "UNLOCKED")
            elif "Verrouillé" in access:
                query = query.filter(CatalogMod.patreon_status == "LOCKED")

            # Sorting
            sort = filter_state["sort"]
            if "Récent" in sort:
                query = query.order_by(CatalogMod.updated_date.desc().nullslast())
            elif "A-Z" in sort:
                query = query.order_by(CatalogMod.title.asc())

            mods = query.limit(100).all()

            # Check platform member sessions
            is_patreon_auth = SessionManager.is_member_authenticated("patreon")
            is_loverslab_auth = SessionManager.is_member_authenticated("loverslab")

            logger.info(
                f"Rafraîchissement catalogue : {len(mods)} mod(s) chargé(s) "
                f"[Filtres: source='{filter_state['source']}', recherche='{filter_state['search']}', statut='{filter_state['status']}'] "
                f"[Compte Membre: LoversLab={'Connecté (✓)' if is_loverslab_auth else 'Non connecté (Invité ✗)'}, Patreon={'Connecté (✓)' if is_patreon_auth else 'Non connecté ✗'}]."
            )

            # Pre-fetch installed mods mapping
            installed_map = {
                (im.source, im.remote_id): im
                for im in session.query(InstalledMod).all()
            }

            if not mods:
                no_data = QLabel("Aucun mod trouvé. Cliquez sur 'Synchroniser' pour alimenter le catalogue.")
                no_data.setStyleSheet("font-size: 14px; color: #64748b; padding: 40px;")
                no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.grid_layout.addWidget(no_data, 0, 0)
                return

            columns = 4
            row = 0
            col = 0
            displayed_count = 0

            for m in mods:
                mod_dict = {
                    "id": m.id,
                    "source": m.source,
                    "remote_id": m.remote_id,
                    "title": m.title,
                    "author": m.author,
                    "page_url": m.page_url,
                    "thumbnail_url": m.thumbnail_url,
                    "updated_date": m.updated_date,
                    "patreon_status": m.patreon_status,
                    "patreon_tier": m.patreon_tier,
                    "external_links": m.get_external_links_list(),
                    "download_urls": m.get_download_urls_list(),
                }

                installed_entry = installed_map.get((m.source, m.remote_id))
                is_installed = installed_entry is not None
                has_update = False
                if is_installed and m.updated_date and installed_entry.version_date:
                    has_update = m.updated_date > installed_entry.version_date

                # Filter by status
                status_filter = filter_state["status"]
                if status_filter == "Déjà installés" and not is_installed:
                    continue
                elif status_filter == "Non installés" and is_installed:
                    continue
                elif status_filter == "Mises à jour disponibles" and not has_update:
                    continue

                card = ModCard(
                    mod_dict,
                    is_installed=is_installed,
                    has_update=has_update,
                    is_patreon_auth=is_patreon_auth,
                    is_loverslab_auth=is_loverslab_auth,
                )
                card.install_requested.connect(self.install_mod)
                self.grid_layout.addWidget(card, row, col)
                displayed_count += 1

                col += 1
                if col >= columns:
                    col = 0
                    row += 1

            logger.debug(f"{displayed_count} tuile(s) affichée(s) dans la grille.")

    def start_sync(self, max_pages: int = 5):
        """Starts background synchronization thread."""
        self.progress_dlg = ProgressDialog("Synchronisation du catalogue", self)
        self.progress_dlg.set_status(f"Lancement de la synchronisation ({max_pages} pages)...")
        self.progress_dlg.set_indeterminate(True)
        self.progress_dlg.show()

        self.sync_worker = SyncWorker(max_pages=max_pages)
        self.sync_worker.progress.connect(self._on_sync_progress)
        self.sync_worker.finished.connect(self._on_sync_finished)
        self.sync_worker.start()

    def _on_sync_progress(self, msg: str, percent: int):
        if hasattr(self, 'progress_dlg') and self.progress_dlg.isVisible():
            self.progress_dlg.set_status(msg)
            if percent > 0:
                self.progress_dlg.set_progress(percent)

    def _on_sync_finished(self, count: int, msg: str):
        if hasattr(self, 'progress_dlg'):
            self.progress_dlg.close()
        QMessageBox.information(self, "Synchronisation terminée", f"{msg}\n{count} nouveaux éléments traités.")
        self.refresh_catalog()

    def install_mod(self, mod_data: dict):
        """Starts background download and installation of selected mod."""
        self.progress_dlg = ProgressDialog(f"Installation de {mod_data.get('title')}", self)
        self.progress_dlg.show()

        self.install_worker = InstallWorker(mod_data)
        self.install_worker.progress.connect(self._on_install_progress)
        self.install_worker.finished.connect(self._on_install_finished)
        self.install_worker.start()

    def _on_install_progress(self, msg: str, percent: int):
        if hasattr(self, 'progress_dlg') and self.progress_dlg.isVisible():
            self.progress_dlg.set_status(msg)
            self.progress_dlg.set_progress(percent)

    def _on_install_finished(self, success: bool, msg: str):
        if hasattr(self, 'progress_dlg'):
            self.progress_dlg.close()
        if success:
            QMessageBox.information(self, "Installation Réussie", msg)
        else:
            QMessageBox.warning(self, "Erreur d'Installation", msg)
        self.refresh_catalog()
