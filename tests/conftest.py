import concurrent.futures
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.api.app import app
from src.core.session_manager import SessionManager
from src.core.shutdown_manager import ShutdownManager
from src.database import DatabaseManager

_tracked_executors = []
_orig_tpe_init = concurrent.futures.ThreadPoolExecutor.__init__


def _tracked_init(self, *args, **kwargs):
    _tracked_executors.append(self)
    _orig_tpe_init(self, *args, **kwargs)


concurrent.futures.ThreadPoolExecutor.__init__ = _tracked_init



@pytest.fixture(autouse=True)
def reset_shutdown_state():
    """Ensure ShutdownManager state is clean before and after every test."""
    ShutdownManager.reset()
    yield
    ShutdownManager.reset()



@pytest.fixture(scope="session", autouse=True)
def isolate_test_database(tmp_path_factory):
    """
    Isole complètement la base de données de test de la base réelle de l'utilisateur.
    Garantit qu'aucun enregistrement de test n'est injecté dans sims4_mods.db.
    """
    test_dir = tmp_path_factory.mktemp("isolated_test_db")
    test_db = test_dir / "sims4_mods_test.db"

    old_env = os.environ.get("SIMS4_DB_PATH")
    os.environ["SIMS4_DB_PATH"] = str(test_db)

    # Réinitialise le singleton pour forcer l'usage du fichier isolé
    DatabaseManager._instance = None
    DatabaseManager.get_instance(str(test_db))

    yield test_db

    # Nettoyage
    if old_env is not None:
        os.environ["SIMS4_DB_PATH"] = old_env
    else:
        os.environ.pop("SIMS4_DB_PATH", None)
    DatabaseManager._instance = None


@pytest.fixture
def client():
    """TestClient FastAPI pré-configuré avec l'instance de base de données de test."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session(tmp_path):
    """Session SQLAlchemy isolée dans un fichier de base de données temporaire."""
    db_file = tmp_path / "test_conftest.db"
    db_mgr = DatabaseManager(str(db_file))
    with db_mgr.get_session() as session:
        yield session




@pytest.fixture(scope="session")
def qapp():
    """QApplication session fixture for UI tests."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if not app:
        app = QApplication(["pytest", "-platform", "offscreen"])
    return app


def pytest_sessionfinish(session, exitstatus):
    """
    Cleanly closes any pooled HTTP sessions, shuts down active ThreadPoolExecutors,
    and terminates any lingering Qt thread pool tasks to ensure clean process termination.
    """
    # 1. Close curl_cffi HTTP sessions
    try:
        SessionManager.close_all_http_sessions()
    except Exception:
        pass

    # 2. Shutdown any tracked ThreadPoolExecutors
    for ex in _tracked_executors:
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    # 3. Clean up Qt threadpool and quit QApplication
    try:
        from PySide6.QtCore import QThreadPool
        from PySide6.QtWidgets import QApplication
        QThreadPool.globalInstance().waitForDone(50)
        app = QApplication.instance()
        if app:
            app.quit()
    except Exception:
        pass






