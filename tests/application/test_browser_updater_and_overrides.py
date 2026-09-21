from unittest.mock import patch, MagicMock
from src.infrastructure.network.browser_updater_service import BrowserUpdaterService
from src.application.dependencies.dependency_resolver import resolve_mod_dependencies
from src.database.models import CatalogMod


def test_browser_updater_is_chromium_ready():
    # Test operational
    with patch("playwright.sync_api.sync_playwright") as mock_sp:
        mock_p = MagicMock()
        mock_p.chromium.executable_path = "C:\\fake\\chrome.exe"
        mock_p.chromium.launch.return_value = MagicMock()
        mock_sp.return_value.__enter__.return_value = mock_p

        with patch("pathlib.Path.exists", return_value=True):
            assert BrowserUpdaterService.is_chromium_ready() is True

    # Test not operational
    with patch("playwright.sync_api.sync_playwright", side_effect=Exception("Playwright not installed")):
        assert BrowserUpdaterService.is_chromium_ready() is False


def test_browser_updater_install_stream_success():
    mock_process = MagicMock()
    mock_process.stdout.readline.side_effect = [
        "Downloading Chromium 119.0 (playwright build v1155)\n",
        "10% of 145.0 MB\n",
        "50% of 145.0 MB\n",
        "100% of 145.0 MB\n",
        "",
    ]
    mock_process.poll.side_effect = [None, None, None, None, 0]
    mock_process.wait.return_value = 0

    progress_events = []

    def on_progress(percent, msg):
        progress_events.append((percent, msg))

    with patch("subprocess.Popen", return_value=mock_process):
        success, message = BrowserUpdaterService.install_chromium_stream(progress_callback=on_progress)
        assert success is True
        assert len(progress_events) >= 3
        percents = [p[0] for p in progress_events]
        assert 10 in percents
        assert 50 in percents
        assert 100 in percents


def test_dependency_resolver_with_requirements_overrides():
    raw_deps = [
        {"title": "XML-Injector"},
        {"title": "You must enable script mods in game options"},
    ]
    mock_session = MagicMock()
    # Mock catalog query returning None for both
    mock_session.query.return_value.filter.return_value.first.return_value = None

    installed_by_remote = {}
    mock_mod = MagicMock(id=1, title="XML Injector", folder_name="XML_Injector", source="loverslab", remote_id="123")
    installed_by_title = {"xml injector": mock_mod}

    # 1. Without overrides: XML-Injector matches XML Injector via canonical fingerprint
    deps = resolve_mod_dependencies(
        raw_deps=raw_deps,
        session=mock_session,
        installed_by_remote=installed_by_remote,
        installed_by_title=installed_by_title,
        is_syncing=False,
        requirements_overrides=None,
    )
    xml_item = next((d for d in deps if "XML" in d.title), None)
    assert xml_item is not None
    assert xml_item.status == "INSTALLED"

    note_item = next((d for d in deps if "game options" in d.title), None)
    assert note_item is not None
    assert note_item.is_comment is False
    assert note_item.status == "NOT_DETECTED_FINISHED"

    # 2. With override: Note is marked as COMMENT
    overrides = {"You must enable script mods in game options": "COMMENT"}
    deps_override = resolve_mod_dependencies(
        raw_deps=raw_deps,
        session=mock_session,
        installed_by_remote=installed_by_remote,
        installed_by_title=installed_by_title,
        is_syncing=False,
        requirements_overrides=overrides,
    )
    comment_item = next((d for d in deps_override if "game options" in d.title), None)
    assert comment_item is not None
    assert comment_item.is_comment is True
    assert comment_item.status == "COMMENT_NOISE"


def test_catalog_mod_requirements_overrides_model():
    mod = CatalogMod(
        source="loverslab",
        remote_id="9999",
        title="Test Mod With Overrides",
        author="AuthorName",
        page_url="https://loverslab.com/files/file/9999-test",
    )
    assert mod.get_requirements_overrides() == {}

    mod.set_requirements_overrides({"Notes on installation": "COMMENT", "Real Mod": "MOD"})
    assert mod.get_requirements_overrides() == {"Notes on installation": "COMMENT", "Real Mod": "MOD"}


def test_dependency_resolver_with_conversation_lock_mod():
    raw_deps = [
        {
            "source": "game_dlc",
            "remote_id": "BASE_GAME",
            "title": "The Sims 4 (Jeu de base)",
            "is_game_dlc": True,
            "dlc_name": "Jeu de base",
            "is_installed": True,
        },
        {"source": "loverslab", "remote_id": "", "title": "Script Mods enabled in Game Options."},
        {"source": "loverslab", "remote_id": "", "title": "No third-party library or framework is required."},
    ]
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None

    # Initially: Base game is GAME_DLC and installed, the others are NOT_DETECTED_FINISHED
    deps = resolve_mod_dependencies(
        raw_deps=raw_deps,
        session=mock_session,
        installed_by_remote={},
        installed_by_title={},
        is_syncing=False,
        requirements_overrides=None,
    )
    bg = next((d for d in deps if d.is_game_dlc), None)
    assert bg is not None
    assert bg.is_installed is True

    unfound = [d for d in deps if d.status == "NOT_DETECTED_FINISHED"]
    assert len(unfound) == 2

    # User qualifies the 2 unfound items as COMMENT
    overrides = {
        "Script Mods enabled in Game Options.": "COMMENT",
        "No third-party library or framework is required.": "COMMENT",
    }
    deps_qualified = resolve_mod_dependencies(
        raw_deps=raw_deps,
        session=mock_session,
        installed_by_remote={},
        installed_by_title={},
        is_syncing=False,
        requirements_overrides=overrides,
    )
    unfound_after = [d for d in deps_qualified if d.status == "NOT_DETECTED_FINISHED" and not d.is_comment]
    assert len(unfound_after) == 0
    comments = [d for d in deps_qualified if d.is_comment]
    assert len(comments) == 2
