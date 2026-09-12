import zipfile

from src.utils.archive import is_archive, extract_archive, create_backup_zip
from src.utils.cache_utils import hash_url, infer_extension, get_cached_image_path


def test_archive_utilities(tmp_path):
    # 1. Non-existent file
    assert is_archive(tmp_path / "ghost.zip") is False

    # 2. DBPF package file (simulated)
    pkg_file = tmp_path / "test.package"
    pkg_file.write_bytes(b"DBPF\x00\x00\x00\x00")
    assert is_archive(pkg_file) is False

    # 3. Valid zip archive
    zip_path = tmp_path / "valid.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("subfolder/file1.package", b"CONTENT_PKG")
        zf.writestr("mod_script.ts4script", b"CONTENT_SCRIPT")

    assert is_archive(zip_path) is True

    # 4. Extract archive
    extract_dir = tmp_path / "extracted"
    extracted_files = extract_archive(zip_path, extract_dir)
    assert len(extracted_files) >= 2
    assert any("file1.package" in str(p) for p in extracted_files)
    assert any("mod_script.ts4script" in str(p) for p in extracted_files)

    # 5. Create backup zip
    backup_path = tmp_path / "backups" / "backup.zip"
    created_backup = create_backup_zip(extract_dir, backup_path)
    assert created_backup.exists()
    assert zipfile.is_zipfile(created_backup)


def test_cache_utils():
    # 1. hash_url deterministic
    url1 = "https://example.com/image.png"
    h1 = hash_url(url1)
    assert len(h1) == 32
    assert hash_url(url1) == h1

    # 2. infer_extension from header or URL
    assert infer_extension("https://example.com/pic.png") == ".png"
    assert infer_extension("https://example.com/pic.webp") == ".webp"
    assert infer_extension("https://example.com/pic.jpeg") == ".jpg"
    assert infer_extension("https://example.com/pic.bin", content_type="image/jpeg") == ".jpg"
    assert infer_extension("https://example.com/unknown") == ".jpg"

    # 3. get_cached_image_path
    p_thumb = get_cached_image_path("https://example.com/t.png", cache_type="thumbnails")
    assert "thumbnails" in str(p_thumb)
    p_screen = get_cached_image_path("https://example.com/s.png", cache_type="screenshots")
    assert "screenshots" in str(p_screen)
    p_desc = get_cached_image_path("https://example.com/d.png", cache_type="desc_images")
    assert "desc_images" in str(p_desc)
    p_gen = get_cached_image_path("https://example.com/g.png", cache_type="images")
    assert "images" in str(p_gen)
