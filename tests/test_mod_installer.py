import zipfile
from src.core.mod_installer import ModInstaller, sanitize_filename
from src.core.mod_toggle import ModToggleManager
from src.core.database import DatabaseManager, InstalledMod
from src.core.config import AppConfig


def test_sanitize_filename():
    assert sanitize_filename('Mod: "Super/Best*Mod?"') == "Mod_SuperBestMod"


def test_install_and_ts4script_depth_fix(tmp_path, monkeypatch):
    # Setup test environment
    mods_dir = tmp_path / "The Sims 4" / "Mods"
    mods_dir.mkdir(parents=True)

    db_file = tmp_path / "test.db"
    db_mgr = DatabaseManager(str(db_file))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    config = AppConfig(custom_mods_dir=str(mods_dir), auto_backup=True)
    monkeypatch.setattr(AppConfig, "load", classmethod(lambda cls: config))

    # Create a mock zip archive with a deeply nested .ts4script and a .package
    zip_path = tmp_path / "test_mod.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("subfolder/deep/core_script.ts4script", "mock ts4script content")
        z.writestr("subfolder/package1.package", "mock package content")

    ok, msg = ModInstaller.install_mod_from_file(
        file_path=zip_path,
        source="loverslab",
        custom_title="AwesomeMod",
    )
    assert ok is True

    installed_folders = list(mods_dir.glob("loverslab_AwesomeMod*"))
    assert len(installed_folders) == 1
    installed_folder = installed_folders[0]
    assert installed_folder.exists()

    # Verify that .ts4script was relocated to direct child of installed_folder (depth 1 from Mods/)
    direct_script = installed_folder / "core_script.ts4script"
    assert direct_script.exists()

    # Verify that .package is present
    package_files = list(installed_folder.rglob("*.package"))
    assert len(package_files) >= 1


def test_toggle_mod_enable_disable(tmp_path, monkeypatch):
    mods_dir = tmp_path / "The Sims 4" / "Mods"
    mods_dir.mkdir(parents=True)

    db_file = tmp_path / "test.db"
    db_mgr = DatabaseManager(str(db_file))
    monkeypatch.setattr(DatabaseManager, "get_instance", classmethod(lambda cls: db_mgr))

    config = AppConfig(custom_mods_dir=str(mods_dir))
    monkeypatch.setattr(AppConfig, "load", classmethod(lambda cls: config))

    # Create mod folder with files
    mod_dir = mods_dir / "loverslab_TestToggle"
    mod_dir.mkdir()
    (mod_dir / "item.package").write_text("package data")
    (mod_dir / "logic.ts4script").write_text("script data")

    with db_mgr.get_session() as session:
        im = InstalledMod(
            title="TestToggle",
            folder_name="loverslab_TestToggle",
            source="loverslab",
            is_enabled=True,
        )
        im.set_installed_files_list(["loverslab_TestToggle/item.package", "loverslab_TestToggle/logic.ts4script"])
        session.add(im)
        session.commit()
        mod_id = im.id

    # 1. Disable mod
    ok, _ = ModToggleManager.toggle_mod(mod_id, target_state=False)
    assert ok is True
    assert (mod_dir / "item.package.disabled").exists()
    assert (mod_dir / "logic.ts4script.disabled").exists()
    assert not (mod_dir / "item.package").exists()

    # 2. Enable mod back
    ok, _ = ModToggleManager.toggle_mod(mod_id, target_state=True)
    assert ok is True
    assert (mod_dir / "item.package").exists()
    assert (mod_dir / "logic.ts4script").exists()
    assert not (mod_dir / "item.package.disabled").exists()
