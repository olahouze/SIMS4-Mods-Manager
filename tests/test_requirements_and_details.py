from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from src.api.app import app
from src.core.database import DatabaseManager, CatalogMod, InstalledMod
from src.providers.loverslab import LoversLabProvider


def test_extract_requirements_variations():
    provider = LoversLabProvider()

    # 1. Base game only -> NONE
    html_base_game = """
    <ul class="cFileInfo">
        <li class="ipsDataItem">
            <span><strong>Requirements</strong></span>
            <div class="cFileInfoData">Sims 4</div>
        </li>
    </ul>
    """
    soup = BeautifulSoup(html_base_game, "html.parser")
    txt, st, mods = provider.extract_requirements(soup)
    assert st == "NONE"
    assert len(mods) == 0

    # 2. LoversLab URL identified -> RESOLVED
    html_resolved = """
    <ul class="cFileInfo">
        <li class="ipsDataItem">
            <span><strong>Requirements</strong></span>
            <div class="cFileInfoData">
                Kritikal's "Atlas Frame" https://www.loverslab.com/files/file/9123-kritical-atlas-frame/
            </div>
        </li>
    </ul>
    """
    soup2 = BeautifulSoup(html_resolved, "html.parser")
    txt2, st2, mods2 = provider.extract_requirements(soup2)
    assert st2 == "RESOLVED"
    assert len(mods2) == 1
    assert mods2[0]["remote_id"] == "9123"
    assert mods2[0]["source"] == "loverslab"

    # 3. Unresolved text requirement -> PENDING_VERIFICATION (captured as pending module)
    html_unresolved = """
    <ul class="cFileInfo">
        <li class="ipsDataItem">
            <span><strong>Requirements</strong></span>
            <div class="cFileInfoData">
                Kritical's Dreams of Surrender und zugehorige Objekte
            </div>
        </li>
    </ul>
    """
    soup3 = BeautifulSoup(html_unresolved, "html.parser")
    txt3, st3, mods3 = provider.extract_requirements(soup3)
    assert st3 == "PENDING_VERIFICATION"
    assert len(mods3) == 1
    assert "Dreams of Surrender" in mods3[0]["title"]
    assert mods3[0]["remote_id"] == ""


def test_extract_multi_requirements_delimiter_splitting():
    """Mod 29732 contains 'Wicked whims-Basemental Drug' which must be split into two distinct requirements."""
    provider = LoversLabProvider()
    html = """
    <ul class="cFileInfo">
        <li class="ipsDataItem">
            <span><strong>Requirements</strong></span>
            <div class="cFileInfoData">Wicked whims-Basemental Drug</div>
        </li>
    </ul>
    """
    soup = BeautifulSoup(html, "html.parser")
    txt, st, mods = provider.extract_requirements(soup)
    assert len(mods) == 2

    titles = [m["title"] for m in mods]
    assert "WickedWhims" in titles
    assert "Basemental Drug" in titles

    # WickedWhims is matched to known remote_id 3169
    ww_mod = next(m for m in mods if m["title"] == "WickedWhims")
    assert ww_mod["remote_id"] == "3169"
    assert "loverslab.com" in ww_mod["url"]

    # Basemental Drug is kept with remote_id "" (pending verification)
    bd_mod = next(m for m in mods if m["title"] == "Basemental Drug")
    assert bd_mod["remote_id"] == ""
    assert st == "PENDING_VERIFICATION"


def test_resolve_mod_dependencies_four_statuses():
    """Tests that dependencies resolve to exactly one of the 4 requested statuses."""
    from src.api.routes.catalog import resolve_mod_dependencies, SyncTracker
    db = DatabaseManager.get_instance()

    with db.get_session() as session:
        # Cleanup
        session.query(CatalogMod).filter(CatalogMod.remote_id.in_(["cat_mod_1", "cat_mod_2", "3169"])).delete()
        session.query(InstalledMod).filter(InstalledMod.remote_id.in_(["inst_mod_1"])).delete()
        session.commit()

        # Add installed mod
        im = InstalledMod(source="loverslab", remote_id="inst_mod_1", title="Installed Dependency", folder_name="Dep1")
        # Add catalog mod (not installed)
        cm = CatalogMod(source="loverslab", remote_id="cat_mod_1", title="Catalog Mod Not Installed", page_url="http://example.com")
        session.add_all([im, cm])
        session.commit()

        installed_by_remote = {("loverslab", "inst_mod_1"): im}
        installed_by_title = {"installed dependency": im}

        # Case A: Sync is NOT running -> NOT_DETECTED_FINISHED
        SyncTracker.is_running = False
        raw_deps = [
            {"source": "loverslab", "remote_id": "inst_mod_1", "title": "Installed Dependency"},
            {"source": "loverslab", "remote_id": "cat_mod_1", "title": "Catalog Mod Not Installed"},
            {"source": "loverslab", "remote_id": "", "title": "Unknown Mod Outside Catalog"},
        ]
        resolved = resolve_mod_dependencies(raw_deps, session, installed_by_remote, installed_by_title)
        assert len(resolved) == 3
        assert resolved[0].status == "INSTALLED"
        assert resolved[0].is_installed is True
        assert resolved[1].status == "DETECTED_NOT_INSTALLED"
        assert resolved[1].is_installed is False
        assert resolved[2].status == "NOT_DETECTED_FINISHED"
        assert resolved[2].is_installed is False

        # Case B: Sync IS running -> NOT_DETECTED_SCANNING
        SyncTracker.is_running = True
        resolved_scanning = resolve_mod_dependencies(raw_deps, session, installed_by_remote, installed_by_title)
        assert resolved_scanning[2].status == "NOT_DETECTED_SCANNING"
        SyncTracker.is_running = False


def test_check_dependencies_endpoint():
    client = TestClient(app)
    db = DatabaseManager.get_instance()

    with db.get_session() as session:
        # Cleanup
        session.query(CatalogMod).filter(CatalogMod.remote_id.in_(["req_test_1", "req_test_2", "dep_test_1"])).delete()
        session.query(InstalledMod).filter(InstalledMod.remote_id.in_(["dep_test_1"])).delete()
        session.commit()

        # Mod 1: Unresolved dependencies -> PENDING_VERIFICATION
        m1 = CatalogMod(
            source="loverslab",
            remote_id="req_test_1",
            title="Unresolved Dep Mod",
            page_url="https://loverslab.com/files/file/req_test_1/",
            requirements_status="PENDING_VERIFICATION",
            requirements_text="External script unknown",
        )

        # Mod 2: Resolved with dep_test_1
        m2 = CatalogMod(
            source="loverslab",
            remote_id="req_test_2",
            title="Resolved Dep Mod",
            page_url="https://loverslab.com/files/file/req_test_2/",
            requirements_status="RESOLVED",
            requirements_text="Needs Dep 1",
        )
        m2.set_requirements_mods_list([
            {
                "source": "loverslab",
                "remote_id": "dep_test_1",
                "title": "Dependency 1",
                "url": "https://loverslab.com/files/file/dep_test_1/",
            }
        ])

        # Installed mod: dep_test_1 is already installed
        inst = InstalledMod(
            source="loverslab",
            remote_id="dep_test_1",
            title="Dependency 1",
            folder_name="LoversLab_Dependency_1",
        )

        session.add_all([m1, m2, inst])
        session.commit()

    # 1. Test check-dependencies on m1 (PENDING_VERIFICATION -> allowed as partial install)
    r1 = client.post("/api/catalog/check-dependencies", json={"source": "loverslab", "remote_id": "req_test_1"})
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["can_install"] is True
    assert data1["is_partial"] is True
    assert "non trouvées" in data1["blocking_reason"] or "partielle" in data1["blocking_reason"]

    # 2. Test check-dependencies on m2 (RESOLVED, dep_test_1 already installed)
    r2 = client.post("/api/catalog/check-dependencies", json={"source": "loverslab", "remote_id": "req_test_2"})
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["can_install"] is True
    assert data2["is_partial"] is False
    assert data2["requirements_status"] == "RESOLVED"
    assert len(data2["already_installed_dependencies"]) == 1
    assert data2["already_installed_dependencies"][0]["remote_id"] == "dep_test_1"
    assert len(data2["missing_dependencies"]) == 0


def test_install_partial_when_pending_verification(monkeypatch):
    """Partial installation must proceed even if requirements are pending verification."""
    client = TestClient(app)
    db = DatabaseManager.get_instance()

    with db.get_session() as session:
        m = session.query(CatalogMod).filter_by(source="loverslab", remote_id="req_test_1").first()
        mod_id = m.id if m else None

    assert mod_id is not None

    from src.providers.loverslab import LoversLabProvider
    from src.core.mod_installer import ModInstaller

    def mock_get_details(self, url):
        return {
            "description": "Mock",
            "download_urls": [{"name": "Direct", "url": f"{url}?do=download"}],
            "external_links": [],
            "requirements_mods": [],
            "requirements_status": "NONE",
            "screenshots": [],
        }

    def mock_download(self, url, dest_path, progress_callback=None):
        dest_path.write_bytes(b"DBPF\x00\x00\x00\x00")
        return True, str(dest_path)

    def mock_install(file_path, catalog_mod, source, custom_title, **kwargs):
        return True, f"Mod '{custom_title}' installé avec succès"

    monkeypatch.setattr(LoversLabProvider, "get_mod_details", mock_get_details)
    monkeypatch.setattr(LoversLabProvider, "download_mod_file", mock_download)
    monkeypatch.setattr(ModInstaller, "install_mod_from_file", mock_install)

    # Attempting to install should succeed with partial install indication
    resp = client.post("/api/catalog/install", json={"catalog_mod_id": mod_id, "allow_partial": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "installé avec succès" in data["message"] or "partielle" in data["message"]


def test_loverslab_14_subcategories_and_worker():
    provider = LoversLabProvider()
    assert len(provider.CATEGORIES) == 14

    category_ids = [c["id"] for c in provider.CATEGORIES]
    assert "174" in category_ids  # WickedWhims
    assert "201" in category_ids  # Animations WW
    assert "215" in category_ids  # Translations WW
    assert "203" in category_ids  # Clothing
    assert "206" in category_ids  # Objects
    assert "216" in category_ids  # Uncategorized

    # Verify get_total_pages runs instantly and equals the sum of estimates
    total_pages = provider.get_total_pages()
    assert total_pages > 350

    # Test dynamic page updating
    provider.update_category_detected_pages("174", 20)
    assert provider._category_pages_cache["174"] == 20


def test_sync_tracker_categories_progress():
    from src.api.routes.catalog import SyncTracker

    provider = LoversLabProvider()
    SyncTracker.start(300, categories_list=provider.CATEGORIES)
    assert SyncTracker.is_running is True
    assert len(SyncTracker.categories) == 14
    assert SyncTracker.providers_status["loverslab"] == "RUNNING"

    # Update category 174 progress
    SyncTracker.update_category("174", pages_completed=5, total_pages=16, mods_count=120, status="IN_PROGRESS")
    resp = SyncTracker.to_response()
    assert resp.is_running is True
    assert len(resp.categories_progress) == 14

    cat_174 = next(c for c in resp.categories_progress if c.id == "174")
    assert cat_174.pages_completed == 5
    assert cat_174.mods_count == 120
    assert cat_174.status == "IN_PROGRESS"

    SyncTracker.finish(total_new=120)
    assert SyncTracker.is_running is False
    assert SyncTracker.providers_status["loverslab"] == "OK"


def test_wickedwhims_all_naming_variations_recognition():
    """
    Validates that WickedWhims is correctly identified and linked to ID 3169
    across all variations: WW, ww, WickedWhims, wickedwhims, Wicked-Whims,
    wicked-whims, Wicked_Whims, wicked_whims, Wicked Whims, WiCkedWhIms, etc.
    """
    from src.providers.loverslab import is_wickedwhims_name, LoversLabProvider
    provider = LoversLabProvider()

    variations = [
        "WW",
        "ww",
        "Ww",
        "WickedWhims",
        "wickedwhims",
        "Wicked-Whims",
        "wicked-whims",
        "Wicked_Whims",
        "wicked_whims",
        "Wicked Whims",
        "wicked whims",
        "WiCkedWhIms",
        "WICKEDWHIMS",
        "Wicked Whim",
        "Wicked-Whim",
        "Wicked_Whim",
    ]

    for var in variations:
        assert is_wickedwhims_name(var) is True, f"Failed for variation: {var}"

        html = f"""
        <ul class="cFileInfo">
            <li class="ipsDataItem">
                <span><strong>Requirements</strong></span>
                <div class="cFileInfoData">{var}</div>
            </li>
        </ul>
        """
        soup = BeautifulSoup(html, "html.parser")
        _, st, mods = provider.extract_requirements(soup)
        assert len(mods) == 1, f"Failed length for: {var}"
        assert mods[0]["remote_id"] == "3169", f"Failed ID mapping for: {var}"
        assert "3169-wickedwhims" in mods[0]["url"]
        assert st == "RESOLVED"

    # Test combined with hyphen delimiter like 'Wicked-Whims - OtherMod'
    html_combo = """
    <ul class="cFileInfo">
        <li class="ipsDataItem">
            <span><strong>Requirements</strong></span>
            <div class="cFileInfoData">Wicked-Whims - OtherMod</div>
        </li>
    </ul>
    """
    soup_combo = BeautifulSoup(html_combo, "html.parser")
    _, _, mods_combo = provider.extract_requirements(soup_combo)
    assert len(mods_combo) == 2
    assert mods_combo[0]["remote_id"] == "3169"
    assert mods_combo[0]["title"] == "WickedWhims"
    assert mods_combo[1]["title"] == "OtherMod"


def test_shutdown_manager_graceful_handling():
    """Validates ShutdownManager registers callbacks and marks shutdown state."""
    from src.core.shutdown_manager import ShutdownManager

    # Reset state for testing
    ShutdownManager._is_shutting_down = False
    callback_fired = []

    def on_shutdown():
        callback_fired.append(True)

    ShutdownManager.register_shutdown_callback(on_shutdown)
    assert ShutdownManager.is_shutting_down() is False

    ShutdownManager.trigger_shutdown()
    assert ShutdownManager.is_shutting_down() is True
    assert len(callback_fired) == 1

    # Calling again is idempotent
    ShutdownManager.trigger_shutdown()
    assert len(callback_fired) == 1

    # Reset for following tests
    ShutdownManager._is_shutting_down = False
    ShutdownManager._callbacks.clear()


def test_wickedwhims_variations_and_br_preservation():
    """Validates robust detection of wickedwhile/wickedwhims variants, line breaks (<br>), and DLC filtering."""
    from src.providers.loverslab import LoversLabProvider, is_wickedwhims_name

    provider = LoversLabProvider()

    # 1. Test is_wickedwhims_name with typos, spacing, versions
    assert is_wickedwhims_name("wickedwhile") is True
    assert is_wickedwhims_name("Wicked While") is True
    assert is_wickedwhims_name("WickedWhims (latest version)") is True
    assert is_wickedwhims_name("Sims 4 WickedWhims") is True
    assert is_wickedwhims_name("wicked-while") is True

    # 2. Test multi-line HTML with <br> separating requirements and EA DLC
    html = """
    <ul class="cFileInfo">
        <li class="ipsDataItem">
            <span><strong>Requirements</strong></span>
            <div class="cFileInfoData">
                WickedWhile<br>
                DLC Sims 4 City Living Expansion Pack
            </div>
        </li>
    </ul>
    """
    soup = BeautifulSoup(html, "html.parser")
    _, st, mods = provider.extract_requirements(soup)

    assert st == "RESOLVED"
    # Should contain WickedWhims (id 3169), but NOT the DLC
    mod_ids = [m.get("remote_id") for m in mods]
    mod_titles = [m.get("title") for m in mods]

    assert "3169" in mod_ids
    assert not any("DLC" in t or "City Living" in t for t in mod_titles)


def test_mod_detail_view_requirements_loading_and_retractable():
    """Validates that ModDetailView shows a loading state during analysis and is collapsible/retractable."""
    from PySide6.QtWidgets import QApplication
    from src.ui.views.mod_detail_view import ModDetailView

    _app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])

    view = ModDetailView()

    # 1. Loading state display
    view._set_requirements_loading()
    assert not view.req_frame.isHidden()
    assert "🔄 Analyse des dépendances" in view.req_title.text()
    assert not view.req_collapse_btn.isHidden()
    assert view.req_collapse_btn.text() == "▲ Réduire"
    assert not view.req_body.isHidden()

    # 2. Toggle collapse
    view.req_collapse_btn.click()
    assert view.req_body.isHidden()
    assert view.req_collapse_btn.text() == "▼ Développer"

    # 3. Toggle expand
    view.req_collapse_btn.click()
    assert not view.req_body.isHidden()
    assert view.req_collapse_btn.text() == "▲ Réduire"

    # 4. Render requirements keeps section interactive and visible
    view._render_requirements({
        "requirements_status": "RESOLVED",
        "requirements_text": "WickedWhims",
        "dependencies": [
            {"remote_id": "3169", "title": "WickedWhims", "status": "DETECTED_NOT_INSTALLED", "is_installed": False}
        ]
    })
    assert not view.req_frame.isHidden()
    assert not view.req_collapse_btn.isHidden()
    assert "Dépendances LoversLab identifiées" in view.req_title.text()
    assert view.deps_layout.count() == 1


def test_cross_view_synchronization_and_panel_counts():
    """Validates cross-view synchronization signals and true indexed mod count in sync panel."""
    from src.core.database import DatabaseManager, CatalogMod
    from src.api.routes.catalog import SyncTracker
    from src.ui.views.catalog_view import CatalogView
    from src.ui.views.installed_view import InstalledView
    from src.ui.views.updates_view import UpdatesView

    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        session.query(CatalogMod).delete()
        session.add(
            CatalogMod(
                source="loverslab",
                remote_id="99901",
                title="Test Mod 1",
                page_url="https://example.com/1",
            )
        )
        session.add(
            CatalogMod(
                source="loverslab",
                remote_id="99902",
                title="Test Mod 2",
                page_url="https://example.com/2",
            )
        )
        session.commit()

    # 1. Test true database count reflected in SyncTracker
    assert db.get_catalog_mods_count() >= 2
    status = SyncTracker.to_response()
    assert status.total_scraped >= 2

    # 2. Test signal declarations in views
    assert hasattr(CatalogView, "install_finished")
    assert hasattr(InstalledView, "mods_changed")
    assert hasattr(UpdatesView, "updates_applied")



