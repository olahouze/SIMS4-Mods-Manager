"""
Module de connexion à la base de données SQLite via SQLAlchemy.
Fournit la création du moteur, la configuration de SessionLocal et l'initialisation des tables.
"""
from typing import Optional
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from src.core.config import AppConfig
from src.database.models import Base


def get_default_db_path() -> str:
    """Retourne le chemin absolu du fichier de base de données par défaut."""
    return str(AppConfig.get_db_path())


def create_db_engine(db_path: Optional[str] = None) -> Engine:
    """Crée et configure le moteur SQLAlchemy pour SQLite avec optimisations de concurrence."""
    path = db_path or get_default_db_path()
    engine = create_engine(f"sqlite:///{path}", echo=False)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Retourne une factory de sessions SQLAlchemy configurée pour l'application."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db_schema(engine: Engine) -> None:
    """Initialise les tables déclaratives dans la base de données si elles n'existent pas."""
    Base.metadata.create_all(engine)
