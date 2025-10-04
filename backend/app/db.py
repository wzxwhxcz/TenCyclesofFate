import sqlite3
import logging
import mysql.connector
from urllib.parse import urlparse
from .config import settings

logger = logging.getLogger(__name__)

def get_db_connection():
    """Establishes and returns a database connection based on the DATABASE_URL."""
    try:
        db_url = settings.DATABASE_URL
        parsed_url = urlparse(db_url)

        if parsed_url.scheme == "sqlite":
            # The user can override the DB path via the DATABASE_URL in .env
            # We need to strip the "sqlite:///" prefix for the connect function.
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            conn = sqlite3.connect(db_path)
            logger.info(f"Successfully connected to SQLite database at: {db_path}")
            return conn
        elif parsed_url.scheme == "mysql":
            conn = mysql.connector.connect(
                host=parsed_url.hostname,
                port=parsed_url.port,
                user=parsed_url.username,
                password=parsed_url.password,
                database=parsed_url.path.lstrip('/')
            )
            logger.info(f"Successfully connected to MySQL database at: {parsed_url.hostname}")
            return conn
        else:
            logger.error(f"Unsupported database scheme: {parsed_url.scheme}")
            return None
            
    except (sqlite3.Error, mysql.connector.Error) as e:
        logger.error(f"Database connection failed to '{settings.DATABASE_URL}': {e}", exc_info=True)
        return None