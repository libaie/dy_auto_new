"""WebSocket connection manager for pairing push notifications."""
from fastapi import WebSocket
import asyncio


class PairWSManager:
    """Manages WebSocket connections for pairing: devices waiting + admin subscribers."""

    def __init__(self):
        # Device connections: pairing_token → WebSocket
        self._device_connections: dict[str, WebSocket] = {}
        # Admin connections: set of WebSockets
        self._admin_connections: set[WebSocket] = set()
        # Device status connections: device_id → WebSocket
        self._device_status_connections: dict[str, WebSocket] = {}

    # --- Device side (waiting for approval) ---

    async def register_device(self, token: str, ws: WebSocket):
        await ws.accept()
        self._device_connections[token] = ws

    def unregister_device(self, token: str):
        self._device_connections.pop(token, None)

    async def notify_device(self, token: str, data: dict):
        """Push result to the waiting device, then close."""
        ws = self._device_connections.pop(token, None)
        if ws:
            try:
                await ws.send_json(data)
                await ws.close()
            except Exception:
                pass

    # --- Admin side (subscribing to events) ---

    async def register_admin(self, ws: WebSocket):
        await ws.accept()
        self._admin_connections.add(ws)

    def unregister_admin(self, ws: WebSocket):
        self._admin_connections.discard(ws)

    async def broadcast_to_admins(self, data: dict):
        """Broadcast event to all connected admin clients."""
        dead = []
        for ws in self._admin_connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._admin_connections.discard(ws)

    async def broadcast_channel_progress(self, channel_id: str, stats: dict):
        """Push channel progress event to admin WS connections."""
        await self.broadcast_to_admins({
            "event": "channel_progress",
            "channel_id": channel_id,
            **stats,
        })

    async def broadcast_channel_completed(self, channel_id: str):
        """Push channel completed event to admin WS connections."""
        await self.broadcast_to_admins({
            "event": "channel_completed",
            "channel_id": channel_id,
        })

    # --- Device status connections (persistent WS for online/offline) ---

    async def register_device_status(self, device_id: str, ws: WebSocket):
        """Register a device's persistent status connection."""
        await ws.accept()
        # If device already has a connection, close the old one
        old = self._device_status_connections.get(device_id)
        if old:
            try:
                await old.close()
            except Exception:
                pass
        self._device_status_connections[device_id] = ws

    def unregister_device_status(self, device_id: str):
        """Remove device status connection (device disconnected)."""
        self._device_status_connections.pop(device_id, None)

    def is_device_online(self, device_id: str) -> bool:
        """Check if device has an active status connection."""
        return device_id in self._device_status_connections

    async def send_to_device(self, device_id: str, data: dict) -> bool:
        """Push a message to a specific device. Returns True if sent."""
        ws = self._device_status_connections.get(device_id)
        if not ws:
            return False
        try:
            await ws.send_json(data)
            return True
        except Exception:
            self._device_status_connections.pop(device_id, None)
            return False

    async def disconnect_device(self, device_id: str) -> bool:
        """Forcefully close a device's status WebSocket connection.

        Returns True if a connection was found and closed.
        The device's onClosing handler will detect the disconnect and
        the server-side ws_device_status handler will mark it offline.
        """
        ws = self._device_status_connections.pop(device_id, None)
        if not ws:
            return False
        try:
            await ws.close(code=4002, reason="Admin forced disconnect")
        except Exception:
            pass
        return True

    async def broadcast_to_devices(self, data: dict):
        """Broadcast a message to all connected devices."""
        dead = []
        for device_id, ws in self._device_status_connections.items():
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(device_id)
        for device_id in dead:
            self._device_status_connections.pop(device_id, None)

    # --- Backward compat aliases ---

    async def register(self, token: str, ws: WebSocket):
        await self.register_device(token, ws)

    def unregister(self, token: str):
        self.unregister_device(token)

    async def notify(self, token: str, data: dict):
        await self.notify_device(token, data)

    def has_connection(self, token: str) -> bool:
        return token in self._device_connections


pair_ws_manager = PairWSManager()
