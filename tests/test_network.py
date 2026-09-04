from pathlib import Path
from unittest.mock import MagicMock
import tempfile

from src.utils.network import is_port_available, find_available_port, is_external_hosted, stream_download


def test_find_available_port():
    port = find_available_port("127.0.0.1", start_port=8000)
    assert isinstance(port, int)
    assert port >= 8000
    assert is_port_available("127.0.0.1", port)


def test_is_external_hosted():
    assert is_external_hosted("https://mega.nz/file/xyz") == "mega.nz"
    assert is_external_hosted("https://www.mediafire.com/download/abc") == "mediafire.com"
    assert is_external_hosted("https://gofile.io/d/1234") == "gofile.io"
    assert is_external_hosted("https://www.loverslab.com/files/file/123-mod") is None
    assert is_external_hosted("https://www.patreon.com/posts/123") is None


def test_stream_download():
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Length": "100"}
    mock_resp.iter_content.return_value = [b"A" * 50, b"B" * 50]

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "test_download.bin"
        cb_calls = []

        def progress_cb(pct, status, detail):
            cb_calls.append((pct, status, detail))

        ok, result_path = stream_download(mock_resp, dest, progress_callback=progress_cb, phase_label="Test")
        assert ok is True
        assert Path(result_path).exists()
        assert dest.read_bytes() == b"A" * 50 + b"B" * 50
