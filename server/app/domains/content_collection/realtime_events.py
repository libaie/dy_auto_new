"""Realtime event helpers for content collection mutations."""
from app.ws_manager import pair_ws_manager


async def broadcast_content_changed():
    await pair_ws_manager.broadcast_to_admins({"event": "content_changed"})


async def broadcast_data_changed(entity_type: str, entity_id):
    await pair_ws_manager.broadcast_to_admins({
        "event": "data_changed",
        "type": entity_type,
        "id": entity_id,
    })
