from src.utils.network import is_port_available, find_available_port


def test_find_available_port():
    port = find_available_port("127.0.0.1", start_port=8000)
    assert isinstance(port, int)
    assert port >= 8000
    assert is_port_available("127.0.0.1", port)
