from unittest.mock import MagicMock
from PySide6.QtWidgets import QMessageBox, QLabel

from src.ui.views.settings_view import SettingsView
from src.ui.views.logs_view import LogsView
from src.ui.views.accounts_view import AccountsView
from src.ui.views.updates_view import UpdatesView
from src.i18n import I18nManager


def test_settings_view_init_and_save(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)

    mock_api = MagicMock()
    mock_api.get_settings.return_value = {
        "custom_mods_dir": "C:/Fake/Mods",
        "custom_game_exe": "",
        "auto_backup": True,
        "adult_content_enabled": True,
        "language": "fr",
        "loverslab_email": "",
        "patreon_email": "",
    }
    mock_api.get_database_stats.return_value = {
        "catalog_mods_count": 10,
        "installed_mods_count": 2,
    }
    mock_api.update_settings.return_value = {"success": True}
    monkeypatch.setattr("src.ui.views.settings_view.get_api_client", lambda: mock_api)

    view = SettingsView()
    try:
        assert view.mods_path_input.text() == "C:/Fake/Mods"
        assert view.backup_chk.isChecked() is True

        # Test language switch
        if "en" in view.lang_buttons:
            view.lang_buttons["en"].click()
            assert I18nManager.instance().get_language() == "en"

        # Restore french
        if "fr" in view.lang_buttons:
            view.lang_buttons["fr"].click()
            assert I18nManager.instance().get_language() == "fr"

        # Test save settings
        view.save_settings()
        assert mock_api.update_settings.call_count == 3
        last_payload = mock_api.update_settings.call_args[0][0]
        assert last_payload["custom_mods_dir"] == "C:/Fake/Mods"
        assert last_payload["language"] == "fr"
    finally:
        view.deleteLater()
        qapp.processEvents()


def test_logs_view_filtering_and_events(qapp, monkeypatch):
    mock_api = MagicMock()
    mock_api.get_logs.return_value = {
        "items": [
            "2026-09-12 [INFO] Initialized app",
            "2026-09-12 [WARNING] Warning test warning",
            "2026-09-12 [ERROR] Fatal disk error",
        ]
    }
    mock_api.clear_logs.return_value = {"deleted_count": 3}
    monkeypatch.setattr("src.ui.views.logs_view.get_api_client", lambda: mock_api)

    view = LogsView()
    try:
        assert len(view.all_logs) == 3

        # Search filter
        view.search_input.setText("Fatal")
        assert "Fatal" in view.log_text.toPlainText()
        assert "Initialized" not in view.log_text.toPlainText()

        # Reset search
        view.search_input.clear()

        # Level filter
        idx = view.level_combo.findData("ERROR")
        if idx >= 0:
            view.level_combo.setCurrentIndex(idx)
            assert "Fatal disk error" in view.log_text.toPlainText()
            assert "Warning test" not in view.log_text.toPlainText()

        # Dynamic log received
        view.level_combo.setCurrentIndex(0)  # All
        view._on_log_received("2026-09-12 [DEBUG] Stream incoming", "DEBUG")
        assert "Stream incoming" in view.log_text.toPlainText()
    finally:
        view.deleteLater()
        qapp.processEvents()


def test_accounts_view(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    mock_api = MagicMock()
    mock_api.get_accounts.return_value = [
        {"provider_name": "loverslab", "is_member": True, "user_display_name": "SimmerLL"},
        {"provider_name": "patreon", "is_member": False, "is_ready": True, "user_display_name": ""},
    ]
    mock_api.clear_account.return_value = {"success": True, "message": "Cleared"}
    monkeypatch.setattr("src.ui.views.accounts_view.get_api_client", lambda: mock_api)

    view = AccountsView()
    try:
        view.refresh_statuses()
        ll_badge = view.findChild(QLabel, "status_loverslab")
        assert ll_badge is not None
        assert "SimmerLL" in ll_badge.text()

        patreon_badge = view.findChild(QLabel, "status_patreon")
        assert patreon_badge is not None

        # Test clear
        view._on_clear_clicked("loverslab")
        mock_api.clear_account.assert_called_once_with("loverslab")

        # Retranslate UI
        view.retranslate_ui()
    finally:
        view.deleteLater()
        qapp.processEvents()


def test_updates_view(qapp, monkeypatch):
    mock_api = MagicMock()
    mock_api.get_updates.return_value = {
        "count": 1,
        "total_installed": 2,
        "items": [
            {
                "installed_id": 1,
                "title": "Animation Pack",
                "folder_name": "anim_pack",
                "source": "loverslab",
                "current_version": "1.0",
                "new_version": "1.1",
                "has_update": True,
            },
            {
                "installed_id": 2,
                "title": "Hair Pack",
                "folder_name": "hair_pack",
                "source": "patreon",
                "current_version": "2.0",
                "new_version": "2.0",
                "has_update": False,
            },
        ]
    }
    monkeypatch.setattr("src.ui.views.updates_view.get_api_client", lambda: mock_api)

    view = UpdatesView()
    try:
        view.refresh_updates()
        assert view.table.rowCount() == 2
        assert view._updatable_count == 1
        assert view.update_selected_btn.isEnabled() is True

        # Filter by search
        view.search_input.setText("Hair")
        assert view.table.rowCount() == 1

        # Clear search
        view.search_input.clear()
        assert view.table.rowCount() == 2
    finally:
        view.deleteLater()
        qapp.processEvents()


def test_catalog_pagination_and_live_sync(qapp, monkeypatch):
    from src.ui.views.catalog_view import CatalogView

    mock_api = MagicMock()
    mock_api.get_accounts.return_value = []
    mock_api.get_catalog.return_value = {
        "items": [
            {
                "id": 1,
                "source": "loverslab",
                "remote_id": "101",
                "title": "Test Mod",
                "author": "Author",
                "page_url": "https://loverslab.com/101",
                "thumbnail_url": "",
                "updated_date": None,
                "patreon_status": "NONE",
                "patreon_tier": "",
                "requirements_text": None,
                "requirements_status": "NONE",
                "dependencies": [],
                "is_installed": False,
                "has_update": False,
            }
        ],
        "total": 50,
        "page": 1,
        "limit": 24,
    }
    mock_api.get_catalog_sync_status.return_value = {
        "is_running": True,
        "is_paused": False,
        "progress_percent": 25,
        "pages_completed": 2,
        "total_pages": 8,
        "current_category": "Clothing",
        "has_error": False,
        "page1_ready": True,
        "categories_progress": [],
    }
    monkeypatch.setattr("src.ui.views.catalog_view.get_api_client", lambda: mock_api)

    view = CatalogView()
    try:
        # Check pagination buttons are properly translated and don't display raw keys
        assert "Précédent" in view.btn_prev.text() or "Previous" in view.btn_prev.text()
        assert "Suivant" in view.btn_next.text() or "Next" in view.btn_next.text()
        assert "catalog.pagination" not in view.btn_prev.text()
        assert "catalog.pagination" not in view.btn_next.text()

        # Execute refresh and wait for events
        view.refresh_catalog()
        qapp.processEvents()

        # Simulate live sync tick that updates pages_done
        view._check_sync_status()
        qapp.processEvents()

        # Successive refresh to ensure no Shiboken deleted object error
        view.refresh_catalog()
        qapp.processEvents()

        # Test retranslate_ui
        view.retranslate_ui()
        assert "catalog.pagination" not in view.btn_prev.text()
    finally:
        view.monitor_timer.stop()
        view.deleteLater()
        qapp.processEvents()

