import socket
from src.utils.logger import logger


def is_port_available(host: str, port: int) -> bool:
    """Checks whether a port is currently available on the specified host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except (OSError, socket.error):
            return False


def find_available_port(host: str = "127.0.0.1", start_port: int = 8000, max_attempts: int = 100) -> int:
    """
    Finds the first free port starting from `start_port`.
    If none in range is available, lets the OS pick an ephemeral free port.
    """
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(host, port):
            if port != start_port:
                logger.info(f"Port par défaut {start_port} indisponible. Port libre alloué : {port}")
            return port

    # Fallback to OS assigned port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        allocated_port = s.getsockname()[1]
        logger.warning(
            f"Plage de ports {start_port}-{start_port + max_attempts} saturée. Port éphémère alloué : {allocated_port}"
        )
        return allocated_port
