import logging
from collections import defaultdict
from .websocket_manager import manager as websocket_manager

logger = logging.getLogger(__name__)

class LiveManager:
    def __init__(self):
        # Key: a player_id being watched (the "broadcaster")
        # Value: a set of player_ids who are watching (the "viewers")
        self.viewers = defaultdict(set)
        # Key: a viewer's player_id
        # Value: the player_id they are currently watching
        self.watching = {}

    def add_viewer(self, viewer_id: str, target_id: str):
        """Adds a viewer to a target's broadcast."""
        if viewer_id in self.watching:
            # If the viewer was watching someone else, remove them from the old group
            self.remove_viewer(viewer_id)
        
        self.viewers[target_id].add(viewer_id)
        self.watching[viewer_id] = target_id
        logger.info(f"Live System: Player '{viewer_id}' is now watching '{target_id}'.")

    def remove_viewer(self, viewer_id: str):
        """Removes a viewer from any broadcast they are watching."""
        if viewer_id in self.watching:
            target_id = self.watching.pop(viewer_id)
            if target_id in self.viewers:
                self.viewers[target_id].remove(viewer_id)
                if not self.viewers[target_id]:
                    # Clean up empty sets
                    del self.viewers[target_id]
            logger.info(f"Live System: Player '{viewer_id}' stopped watching '{target_id}'.")

    async def broadcast_state_update(self, target_id: str, state: dict):
        """Broadcasts a state update to all viewers of a target player."""
        if target_id in self.viewers:
            viewer_list = list(self.viewers[target_id])
            logger.info(f"Live System: Broadcasting state of '{target_id}' to {len(viewer_list)} viewers. First one is '{viewer_list[0]}'." if viewer_list else "No viewers to broadcast to.")
            for viewer_id in viewer_list:
                # The data is the state of the *target* player
                await websocket_manager.send_json_to_player(
                    viewer_id, {"type": "live_update", "data": state}
                )

# Create a single instance of the manager
live_manager = LiveManager()