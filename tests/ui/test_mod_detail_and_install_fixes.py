from datetime import datetime
from unittest.mock import MagicMock, patch
from src.api.schemas.catalog import CatalogInstallRequest
from src.api.client import ApiClient
from src.ui.views.mod_detail.detail_requirements import DetailRequirementsWidget


def test_catalog_install_request_date_parsing():
    # 1. Standard ISO date string
    r1 = CatalogInstallRequest(title="Mod 1", updated_date="2026-09-18T07:45:00")
    assert isinstance(r1.updated_date, datetime)
    assert r1.updated_date.year == 2026

    # 2. French formatted date string (DD/MM/YYYY)
    r2 = CatalogInstallRequest(title="Mod 2", updated_date="18/09/2026")
    assert isinstance(r2.updated_date, datetime)
    assert r2.updated_date.day == 18
    assert r2.updated_date.month == 9
    assert r2.updated_date.year == 2026

    # 3. None or empty string
    r3 = CatalogInstallRequest(title="Mod 3", updated_date="")
    assert r3.updated_date is None

    r4 = CatalogInstallRequest(title="Mod 4", updated_date=None)
    assert r4.updated_date is None

    # 4. Invalid string does not raise 422 validation error
    r5 = CatalogInstallRequest(title="Mod 5", updated_date="invalid-date-string")
    assert r5.updated_date is None


def test_api_client_check_dependencies_with_int():
    client = ApiClient()
    mock_post = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True, "already_installed_dependencies": []}
    mock_post.return_value = mock_resp

    with patch.object(client._client, "post", mock_post):
        # 1. Pass integer
        res = client.check_dependencies(42)
        assert res["success"] is True
        mock_post.assert_called_with("/api/catalog/check-dependencies", json={"catalog_mod_id": 42})

        # 2. Pass dict
        payload = {"catalog_mod_id": 10, "source": "loverslab"}
        client.check_dependencies(payload)
        mock_post.assert_called_with("/api/catalog/check-dependencies", json=payload)


def test_detail_requirements_widget_no_synthetic_duplicate(qapp):
    widget = DetailRequirementsWidget()

    # Simulate mod 39061 Shrike60 Animations data:
    # req_text is "Wicked Whims, Kritical Devices"
    # req_status is "PENDING_VERIFICATION"
    # raw dependencies were already extracted
    data = {
        "requirements_text": "Wicked Whims, Kritical Devices",
        "requirements_status": "PENDING_VERIFICATION",
        "dependencies": [
            {
                "source": "loverslab",
                "remote_id": "3169",
                "title": "WickedWhims",
                "url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
                "is_installed": True,
                "status": "INSTALLED",
            },
            {
                "source": "loverslab",
                "remote_id": "21924",
                "title": "DD for Kritical's Devices",
                "url": "https://www.loverslab.com/files/file/21924-dd-for-kriticals-devices/",
                "is_installed": False,
                "status": "DETECTED_NOT_INSTALLED",
            },
        ],
    }

    res = widget.render_requirements(data)

    # Verify that NO synthetic entry containing "Wicked Whims, Kritical Devices" was created
    unfound = res.get("unfound", [])
    to_install = res.get("to_install", [])
    already_installed = res.get("already_installed", [])

    assert len(already_installed) == 1
    assert already_installed[0]["title"] == "WickedWhims"
    assert len(to_install) == 1
    assert to_install[0]["title"] == "DD for Kritical's Devices"
    assert len(unfound) == 0, f"Expected 0 unfound entries, got: {[u['title'] for u in unfound]}"


def test_dialog_helper_information_and_success(qapp):
    from src.ui.utils.dialog_helper import DialogHelper
    with patch("PySide6.QtWidgets.QMessageBox.exec") as mock_exec:
        # 1. DialogHelper.information
        DialogHelper.information(None, "Info Title", "Info Message")
        assert mock_exec.called
        mock_exec.reset_mock()

        # 2. DialogHelper.success
        DialogHelper.success(None, "Success Title", "Success Message")
        assert mock_exec.called


def test_installed_view_delete_mod_scenarios(qapp):
    from src.ui.views.installed_view import InstalledView
    from src.ui.utils.dialog_helper import DialogHelper

    mock_api = MagicMock()
    mock_api.get_installed_mods.return_value = {"items": []}
    mock_api.get_mod_dependents.return_value = {"dependents": []}
    mock_api.uninstall_mod.return_value = {"success": True, "message": "Mod supprimé"}

    view = InstalledView(api_client=mock_api)

    # 1. User cancels confirmation -> uninstall_mod should NOT be called
    with patch.object(DialogHelper, "confirm", return_value=False):
        view._on_delete_mod({"id": 1, "title": "Test Mod", "folder_name": "mod_1"})
        mock_api.uninstall_mod.assert_not_called()

    # 2. User confirms deletion without dependents -> uninstall_mod called and success shown
    with patch.object(DialogHelper, "confirm", return_value=True), \
         patch.object(DialogHelper, "success") as mock_success:
        view._on_delete_mod({"id": 1, "title": "Test Mod", "folder_name": "mod_1"})
        mock_api.uninstall_mod.assert_called_once_with(1)
        mock_success.assert_called_once()

    # 3. Deletion with dependent mods detected -> warning dialog shown, user confirms
    mock_api.uninstall_mod.reset_mock()
    mock_api.get_mod_dependents.return_value = {
        "dependents": [{"title": "Dependent Mod", "folder_name": "mod_dep"}]
    }

    with patch.object(DialogHelper, "confirm", return_value=True) as mock_confirm, \
         patch.object(DialogHelper, "success") as mock_success:
        view._on_delete_mod({"id": 2, "title": "Base Mod", "folder_name": "mod_base"})
        mock_confirm.assert_called_once()
        assert mock_confirm.call_args[1].get("is_destructive") is True
        mock_api.uninstall_mod.assert_called_once_with(2)
        mock_success.assert_called_once()
