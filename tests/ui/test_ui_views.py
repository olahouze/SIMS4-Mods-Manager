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
