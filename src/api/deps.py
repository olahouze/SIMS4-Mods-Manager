from typing import Generator
from sqlalchemy.orm import Session

from src.database.manager import DatabaseManager


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a SQLAlchemy database session
    and guarantees proper closing upon request completion.
    """
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        yield session
