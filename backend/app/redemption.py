import uuid
import time
import logging

from . import db

logger = logging.getLogger(__name__)

def generate_and_insert_redemption_code(user_id: int, quota: float, name: str) -> str | None:
    """
    Generates a unique redemption code and inserts it into the database.

    Args:
        user_id: The integer ID of the user who generated the code.
        quota: The value of the redemption code.
        name: A name or description for the redemption code.

    Returns:
        The generated redemption code string, or None if an error occurred.
    """
    redemption_key = uuid.uuid4().hex.upper()
    current_timestamp = int(time.time())

    conn = None
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO redemptions (user_id, key, status, name, quota, created_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, redemption_key, 1, name, int(quota), current_timestamp)
        )
        conn.commit()
        logger.info(f"Successfully inserted redemption code '{redemption_key}' for user '{user_id}' with quota {quota}.")
        return redemption_key
        
    except Exception as e:
        logger.error(f"Failed to insert redemption code for user '{user_id}': {e}", exc_info=True)
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()