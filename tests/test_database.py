import pytest
from datetime import datetime
from src.core.database import DatabaseManager, CatalogMod, InstalledMod, AccountSession


@pytest.fixture
def db_session(tmp_path):
    db_file = tmp_path / "test.db"
    db_mgr = DatabaseManager(str(db_file))
    with db_mgr.get_session() as session:
        yield session


def test_catalog_mod_crud(db_session):
    mod = CatalogMod(
        source="loverslab",
        remote_id="12345",
        title="Test Sims 4 Mod",
        author="ModderX",
        category="The Sims 4",
        page_url="https://www.loverslab.com/files/file/12345-test/",
        thumbnail_url="https://www.loverslab.com/thumb.jpg",
        published_date=datetime(2025, 1, 1),
        updated_date=datetime(2025, 2, 1),
        patreon_status="PUBLIC",
    )
    mod.set_tags_list(["Animation", "Poses"])
    mod.set_download_urls_list([{"name": "Download", "url": "https://example.com/file.zip"}])

    db_session.add(mod)
    db_session.commit()

    retrieved = db_session.query(CatalogMod).filter_by(source="loverslab", remote_id="12345").first()
    assert retrieved is not None
    assert retrieved.title == "Test Sims 4 Mod"
    assert "Animation" in retrieved.get_tags_list()
    assert len(retrieved.get_download_urls_list()) == 1


def test_installed_mod_and_update_detection(db_session):
    old_date = datetime(2025, 1, 1)
    new_date = datetime(2025, 2, 1)

    cat_mod = CatalogMod(
        source="loverslab",
        remote_id="999",
        title="WickedMod",
        author="AuthorA",
        page_url="https://example.com",
        updated_date=new_date,
    )
    db_session.add(cat_mod)
    db_session.commit()

    installed = InstalledMod(
        catalog_mod_id=cat_mod.id,
        source="loverslab",
        remote_id="999",
        title="WickedMod",
        folder_name="loverslab_WickedMod",
        version_date=old_date,
        is_enabled=True,
    )
    db_session.add(installed)
    db_session.commit()

    # Check update condition
    has_update = cat_mod.updated_date > installed.version_date
    assert has_update is True


def test_account_session_cookies(db_session):
    acc = AccountSession(provider_name="loverslab", is_authenticated=True, user_display_name="SimsPlayer")
    acc.set_cookies_dict({"ips4_member_id": "999", "ips4_login_key": "secret123"})
    db_session.add(acc)
    db_session.commit()

    loaded = db_session.query(AccountSession).filter_by(provider_name="loverslab").first()
    assert loaded is not None
    assert loaded.get_cookies_dict()["ips4_member_id"] == "999"
