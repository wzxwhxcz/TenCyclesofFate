import sqlite3
import logging
from .config import settings

logger = logging.getLogger(__name__)

def get_db_connection():
    """Establishes and returns a connection to the SQLite database."""
    try:
        # The user can override the DB path via the DATABASE_URL in .env
        # We need to strip the "sqlite:///" prefix for the connect function.
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        conn = sqlite3.connect(db_path)
        logger.info(f"Successfully connected to database at: {db_path}")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection failed to '{settings.DATABASE_URL}': {e}", exc_info=True)
        return None