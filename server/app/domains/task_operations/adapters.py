"""Adapter handles for external task-operations dependencies."""

from app.services.channel_service import channel_service
from app.services.content_service import content_service
from app.services.task_service import task_service
from app.ws_manager import pair_ws_manager

__all__ = [
    "channel_service",
    "content_service",
    "pair_ws_manager",
    "task_service",
]
