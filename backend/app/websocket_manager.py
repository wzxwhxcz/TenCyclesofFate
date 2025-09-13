import logging
import copy
import gzip
import json
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Maps player_id to their active WebSocket connection
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, player_id: str):
        """Accepts a new WebSocket connection and stores it."""
        await websocket.accept()
        self.active_connections[player_id] = websocket
        logger.info(f"Player '{player_id}' connected via WebSocket.")

    def disconnect(self, player_id: str):
        """Removes a player's WebSocket connection."""
        if player_id in self.active_connections:
            del self.active_connections[player_id]
            logger.info(f"Player '{player_id}' disconnected from WebSocket.")

    async def send_json_to_player(self, player_id: str, data: dict):
        """Sends a JSON message to a specific player, compressing it with gzip."""
        websocket = self.active_connections.get(player_id)
        if not websocket:
            return

        payload_to_send = data
        if data and data.get("type") in ["full_state", "live_update"]:
            # Deep copy to avoid modifying the original session object in memory
            payload_to_send = copy.deepcopy(data)
            if payload_to_send.get("data"):
                payload_to_send["data"].pop("internal_history", None)
        
        try:
            # 1. Serialize dict to JSON string
            json_str = json.dumps(payload_to_send)
            # 2. Encode string to bytes
            json_bytes = json_str.encode('utf-8')
            # 3. Compress bytes using gzip
            compressed_data = gzip.compress(json_bytes)
            # 4. Send compressed bytes
            await websocket.send_bytes(compressed_data)
        except (WebSocketDisconnect, RuntimeError) as e:
            logger.warning(f"WebSocket for player '{player_id}' disconnected before message could be sent: {e}")
            self.disconnect(player_id)

# Create a single instance of the manager to be used across the application
manager = ConnectionManager()