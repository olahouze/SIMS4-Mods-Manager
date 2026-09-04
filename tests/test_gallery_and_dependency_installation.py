from fastapi.testclient import TestClient
from src.api.app import app
from src.core.database import DatabaseManager, CatalogMod, InstalledMod
from src.ui.components.image_viewer_modal import ImageViewerModal


def test_mod_details_response_has_screenshots():
    client = TestClient(app)
    db = DatabaseManager.get_instance()

    with db.get_session() as session:
        # Create a test catalog mod with description containing an image
        session.query(CatalogMod).filter_by(remote_id="gallery_test_1").delete()
        session.commit()

        mod = CatalogMod(
            source="loverslab",
            remote_id="gallery_test_1",
            title="Gallery Test Mod",
            page_url="https://loverslab.com/files/file/gallery_test_1/",
            description='<p>Sample mod</p><img src="https://static.loverslab.com/screenshots/monthly_2024/test.jpg">',
        )
        session.add(mod)
        session.commit()
        mod_id = mod.id

    resp = client.get(f"/api/catalog/{mod_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "screenshots" in data
    assert isinstance(data["screenshots"], list)
    assert len(data["screenshots"]) >= 1
    assert "https://static.loverslab.com/screenshots/monthly_2024/test.jpg" in data["screenshots"]


def test_image_viewer_modal_instantiation():
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])
    images = [
        "https://static.loverslab.com/screenshots/1.jpg",
        "https://static.loverslab.com/screenshots/2.jpg",
    ]
    modal = ImageViewerModal(images, current_index=0)
    assert modal.images == images
    assert modal.current_index == 0
    assert modal.counter_lbl.text() == "Photo 1 / 2"


def test_cascade_dependency_installation_flow(monkeypatch):
    """
    Simulates installing a parent mod with a missing dependency and verifies
    that both the dependency and the parent mod are sequentially processed.
    """
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        session.query(CatalogMod).filter(CatalogMod.remote_id.in_(["parent_mod_1", "child_dep_1"])).delete()
        session.query(InstalledMod).filter(InstalledMod.remote_id.in_(["parent_mod_1", "child_dep_1"])).delete()
        session.commit()

        dep_mod = CatalogMod(
            source="loverslab",
            remote_id="child_dep_1",
            title="Child Dependency Mod",
            page_url="https://loverslab.com/files/file/child_dep_1/",
            requirements_status="NONE",
        )
        session.add(dep_mod)

        parent_mod = CatalogMod(
            source="loverslab",
            remote_id="parent_mod_1",
            title="Parent Mod with Dep",
            page_url="https://loverslab.com/files/file/parent_mod_1/",
            requirements_status="RESOLVED",
        )
        parent_mod.set_requirements_mods_list([
            {
                "source": "loverslab",
                "remote_id": "child_dep_1",
                "title": "Child Dependency Mod",
                "url": "https://loverslab.com/files/file/child_dep_1/",
            }
        ])
        session.add(parent_mod)
        session.commit()
        parent_id = parent_mod.id

    client = TestClient(app)

    installed_calls = []

    # Mock provider and installer to track sequential calls
    from src.providers.loverslab import LoversLabProvider
    from src.core.mod_installer import ModInstaller

    def mock_get_mod_details(self, url):
        return {
            "description": "Mock description",
            "download_urls": [{"name": "Direct", "url": f"{url}?do=download"}],
            "external_links": [],
            "requirements_mods": [],
            "requirements_status": "NONE",
            "screenshots": [],
        }

    def mock_download_mod_file(self, url, dest_path, progress_callback=None):
        dest_path.write_bytes(b"DBPF\x00\x00\x00\x00")
        return True, str(dest_path)

    def mock_install_mod_from_file(file_path, catalog_mod, source, custom_title, **kwargs):
        installed_calls.append(custom_title)
        # Create InstalledMod record so dependency check sees it as installed
        with db.get_session() as s:
            rec = InstalledMod(
                source=source,
                remote_id=catalog_mod.remote_id if catalog_mod else "custom",
                title=custom_title,
                folder_name=f"Mock_{custom_title.replace(' ', '_')}",
                is_enabled=True,
            )
            s.add(rec)
            s.commit()
        return True, "Installation mock réussie"

    monkeypatch.setattr(LoversLabProvider, "get_mod_details", mock_get_mod_details)
    monkeypatch.setattr(LoversLabProvider, "download_mod_file", mock_download_mod_file)
    monkeypatch.setattr(ModInstaller, "install_mod_from_file", mock_install_mod_from_file)

    resp = client.post("/api/catalog/install", json={"catalog_mod_id": parent_id, "install_dependencies": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    # The dependency must be installed BEFORE the parent mod!
    assert "Child Dependency Mod" in installed_calls
    assert "Parent Mod with Dep" in installed_calls
    assert installed_calls.index("Child Dependency Mod") < installed_calls.index("Parent Mod with Dep")
    assert "Child Dependency Mod" in data["installed_dependencies"]


def test_extract_download_candidates_prioritizes_zip_over_external():
    from bs4 import BeautifulSoup
    from src.providers.loverslab import LoversLabProvider

    provider = LoversLabProvider()
    html = """
    <ul class="ipsDataList">
        <li class="ipsDataItem" data-rowid="1">
            <h4 class="ipsDataItem_title">wickedwhims</h4>
            <div class="ipsType_light ipsDataItem_meta">/July 24, 2023</div>
            <a href="https://www.loverslab.com/files/file/3169/?do=download&r=1" data-action="download">Download</a>
        </li>
        <li class="ipsDataItem" data-rowid="2">
            <h4 class="ipsDataItem_title">WickedWhims v185k - PUBLIC - 23 May 2026.zip</h4>
            <div class="ipsType_light ipsDataItem_meta">139.43 MB/May 23</div>
            <a href="https://www.loverslab.com/files/file/3169/?do=download&r=2" data-action="download">Download</a>
        </li>
    </ul>
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates = provider._extract_download_candidates(soup, "https://www.loverslab.com")
    assert len(candidates) == 2
    # The direct zip archive candidate with file size MUST be first (highest score)
    assert candidates[0]["title"] == "WickedWhims v185k - PUBLIC - 23 May 2026.zip"
    assert "r=2" in candidates[0]["url"]
    assert candidates[0]["score"] > candidates[1]["score"]


def test_dependency_failure_aborts_main_installation(monkeypatch):
    """If a required dependency fails to install, the parent mod must NOT be installed."""
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        session.query(CatalogMod).filter(CatalogMod.remote_id.in_(["fail_parent", "fail_dep"])).delete()
        session.commit()

        dep_mod = CatalogMod(
            source="loverslab",
            remote_id="fail_dep",
            title="Failing Dependency Mod",
            page_url="https://loverslab.com/files/file/fail_dep/",
            requirements_status="NONE",
        )
        parent_mod = CatalogMod(
            source="loverslab",
            remote_id="fail_parent",
            title="Parent Mod Blocked",
            page_url="https://loverslab.com/files/file/fail_parent/",
            requirements_status="RESOLVED",
        )
        parent_mod.set_requirements_mods_list([
            {"source": "loverslab", "remote_id": "fail_dep", "title": "Failing Dependency Mod", "url": "https://loverslab.com/files/file/fail_dep/"}
        ])
        session.add_all([dep_mod, parent_mod])
        session.commit()
        parent_id = parent_mod.id

    client = TestClient(app)
    from src.providers.loverslab import LoversLabProvider

    # Mock details
    def mock_get_details(self, url):
        return {
            "description": "Mock",
            "download_urls": [{"name": "Direct", "url": f"{url}?do=download"}],
            "external_links": [],
            "requirements_mods": [],
            "requirements_status": "NONE",
            "screenshots": [],
        }

    # Mock download where dependency download FAILS
    def mock_download_fail(self, url, dest_path, progress_callback=None):
        if "fail_dep" in url:
            return False, "Échec du téléchargement final (Code HTTP 403)"
        return True, str(dest_path)

    monkeypatch.setattr(LoversLabProvider, "get_mod_details", mock_get_details)
    monkeypatch.setattr(LoversLabProvider, "download_mod_file", mock_download_fail)

    resp = client.post("/api/catalog/install", json={"catalog_mod_id": parent_id, "install_dependencies": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "Installation interrompue" in data["message"]
    assert "Failing Dependency Mod" in data["message"]


def test_dependencies_dialog_partial_installation():
    from PySide6.QtWidgets import QApplication
    from src.ui.components.dependencies_dialog import DependenciesDialog

    _app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])
    unfound = [{"title": "Unfound External Mod", "remote_id": ""}]
    already = [{"title": "Installed Mod A", "remote_id": "100"}]
    missing = [{"title": "Found Mod B", "remote_id": "200"}]

    dlg = DependenciesDialog(
        mod_title="Test Partial Mod",
        already_installed=already,
        missing=missing,
        unfound=unfound,
        is_partial=True,
    )
    assert dlg.is_partial is True
    assert "Installation Partielle" in dlg.windowTitle()

    # Find the confirm button
    from PySide6.QtWidgets import QPushButton
    buttons = dlg.findChildren(QPushButton)
    confirm_btn = next((b for b in buttons if "Partielle" in b.text()), None)
    assert confirm_btn is not None
    assert "Installation Partielle" in confirm_btn.text()
