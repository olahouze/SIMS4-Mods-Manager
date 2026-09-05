from datetime import datetime, timedelta
from unittest.mock import MagicMock

from src.database import InstalledMod, CatalogMod
from src.services.mod_update_service import check_has_update, resolve_catalog_mod


def test_check_has_update_newer_date():
    now = datetime.now()
    older = now - timedelta(days=2)
    im = InstalledMod(title="TestMod", folder_name="TestMod", version_date=older)
    cm = CatalogMod(title="TestMod", updated_date=now)
    assert check_has_update(im, cm) is True


def test_check_has_update_same_date():
    now = datetime.now()
    im = InstalledMod(title="TestMod", folder_name="TestMod", version_date=now)
    cm = CatalogMod(title="TestMod", updated_date=now)
    assert check_has_update(im, cm) is False


def test_check_has_update_version_string_diff():
    now = datetime.now()
    im = InstalledMod(title="TestMod", folder_name="TestMod", version_date=now, version_str="1.0.0")
    cm = CatalogMod(title="TestMod", updated_date=now, version_str="1.1.0")
    assert check_has_update(im, cm) is True


def test_check_has_update_no_installed_date():
    now = datetime.now()
    im = InstalledMod(title="TestMod", folder_name="TestMod", version_date=None)
    cm = CatalogMod(title="TestMod", updated_date=now)
    assert check_has_update(im, cm) is True


def test_check_has_update_no_catalog_mod():
    im = InstalledMod(title="TestMod", folder_name="TestMod", version_date=datetime.now())
    assert check_has_update(im, None) is False


def test_resolve_catalog_mod_by_remote_id():
    mock_session = MagicMock()
    im = InstalledMod(title="Test", folder_name="Test", source="loverslab", remote_id="12345")
    mock_cat = CatalogMod(id=99, source="loverslab", remote_id="12345")
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_cat

    resolved = resolve_catalog_mod(mock_session, im)
    assert resolved == mock_cat
    assert im.catalog_mod_id == 99
