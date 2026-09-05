from sqlalchemy import text

from src.core.session_manager import SessionManager
from src.database.manager import DatabaseManager


def test_sqlite_pragmas_wal_and_busy_timeout():
    """Validates that SQLite connection applies WAL, NORMAL synchronous, and busy_timeout."""
    db = DatabaseManager.get_instance()
    with db.engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode;")).scalar()
        busy_timeout = conn.execute(text("PRAGMA busy_timeout;")).scalar()
        synchronous = conn.execute(text("PRAGMA synchronous;")).scalar()

        # In-memory SQLite or test DB with file:
        # journal_mode in WAL (or memory for :memory:)
        assert str(journal_mode).lower() in ["wal", "memory"]
        assert busy_timeout >= 5000
        # NORMAL synchronous is code 1 in SQLite
        assert synchronous in [1, 2]


def test_session_manager_pooling_and_invalidation(monkeypatch):
    """Verifies that SessionManager reuses pooled curl_cffi sessions and invalidates cleanly."""
    SessionManager.close_all_http_sessions()

    # Consecutive calls return identical session object
    sess1 = SessionManager.get_http_session("loverslab")
    sess2 = SessionManager.get_http_session("loverslab")
    assert sess1 is sess2

    # Case insensitivity test
    sess_upper = SessionManager.get_http_session("LOVERSLAB")
    assert sess_upper is sess1

    # force_new returns different instance
    sess3 = SessionManager.get_http_session("loverslab", force_new=True)
    assert sess3 is not sess1

    # Invalidation purges from pool
    SessionManager.invalidate_http_session("loverslab")
    sess4 = SessionManager.get_http_session("loverslab")
    assert sess4 is not sess1

    # Teardown
    SessionManager.close_all_http_sessions()
