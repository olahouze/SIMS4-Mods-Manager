import os
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.database import DatabaseManager


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
        app = QApplication([])
    return app
