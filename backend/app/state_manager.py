import asyncio
import json
import logging
from pathlib import Path
from .websocket_manager import manager as websocket_manager

# --- Module-level State ---
SESSIONS: dict[str, dict] = {}
_sessions_modified: bool = False
_data_file_path: Path = Path("game_data.json")
_auto_save_interval: int = 300  # 5 minutes

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Core Functions ---
def load_from_json():
    """Load game sessions from the JSON file at startup."""
    global SESSIONS
    if _data_file_path.exists():
        try:
            with open(_data_file_path, "r", encoding="utf-8") as f:
                SESSIONS = json.load(f)
            logger.info(f"Successfully loaded data from {_data_file_path}")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Could not load data from {_data_file_path}: {e}")
            SESSIONS = {}
    else:
        logger.info(f"{_data_file_path} not found. Starting with empty sessions.")
        SESSIONS = {}

def save_to_json():
    """Save the current sessions to the JSON file."""
    global _sessions_modified
    try:
        with open(_data_file_path, "w", encoding="utf-8") as f:
            json.dump(SESSIONS, f, ensure_ascii=False, indent=4)
        _sessions_modified = False
        logger.info(f"Successfully saved data to {_data_file_path}")
    except IOError as e:
        logger.error(f"Could not save data to {_data_file_path}: {e}")

async def _auto_save_task():
    """Periodically check if data needs to be saved."""
    while True:
        await asyncio.sleep(_auto_save_interval)
        if _sessions_modified:
            logger.info("Auto-saving modified data...")
            save_to_json()

def start_auto_save_task():
    """Creates and starts the background auto-save task."""
    logger.info(f"Starting auto-save task. Interval: {_auto_save_interval} seconds.")
    asyncio.create_task(_auto_save_task())

async def save_session(player_id: str, session_data: dict):
    """
    Saves the entire session data for a player and pushes it to their WebSocket.
    """
    global _sessions_modified
    
    # Check if the new session is the same as the existing one using JSON comparison
    # existing_session = SESSIONS.get(player_id)
    # if existing_session is not None:
    #     try:
    #         if json.dumps(existing_session, sort_keys=True) == json.dumps(session_data, sort_keys=True):
    #             return
    #     except (TypeError, ValueError) as e:
    #         logger.warning(f"Could not compare sessions for player {player_id}: {e}")
    
    SESSIONS[player_id] = session_data
    _sessions_modified = True
    
    # Push the new state to the client via WebSocket
    # await websocket_manager.send_json_to_player(
    #     player_id, {"type": "full_state", "data": session_data}
    # )
    
    asyncio.create_task(
        websocket_manager.send_json_to_player(
            player_id, {"type": "full_state", "data": session_data}
        )
    )


async def get_last_n_inputs(player_id: str, n: int) -> list[str]:
    """Get the last N player inputs for a session."""
    session = SESSIONS.get(player_id, {})
    internal_history = session.get("internal_history", [])
    
    # Filter for user inputs and get the content
    player_inputs = [
        item["content"]
        for item in internal_history
        if isinstance(item, dict) and item.get("role") == "user"
    ]
    
    return player_inputs[-n:]

async def get_session(player_id: str) -> dict | None:
    """Gets the entire session object, which might contain metadata."""
    return SESSIONS.get(player_id)

async def create_or_get_session(player_id: str) -> dict:
    """Creates a session if it doesn't exist, and returns it."""
    global _sessions_modified
    if player_id not in SESSIONS:
        SESSIONS[player_id] = {}  # A session is now a dictionary
        _sessions_modified = True
    return SESSIONS[player_id]

async def clear_session(player_id: str):
    """Clears all data for a given player's session."""
    global _sessions_modified
    if player_id in SESSIONS:
        SESSIONS[player_id] = {} # Reset to an empty dictionary
        _sessions_modified = True
        logger.info(f"Session for player {player_id} has been cleared.")

async def flag_player_for_punishment(player_id: str, level: str, reason: str):
    """Flags a player's session for punishment to be handled by game_logic."""
    global _sessions_modified
    session = SESSIONS.get(player_id)
    if not session:
        logger.warning(f"Attempted to flag non-existent session for player {player_id}")
        return

    # Add the flag directly to the session object.
    session["pending_punishment"] = {
        "level": level,
        "reason": reason
    }
    _sessions_modified = True
    logger.info(f"Player {player_id} flagged for {level} punishment. Reason: {reason}")
    # Immediately notify the client about the punishment flag
    await websocket_manager.send_json_to_player(
        player_id, {"type": "full_state", "data": session}
    )