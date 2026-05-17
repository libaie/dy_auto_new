"""WebSocket connection manager for pairing push notifications."""
from fastapi import WebSocket
import asyncio


class PairWSManager:
    """Manages WebSocket connections for pairing: devices waiting + admin subscribers."""

    def __init__(self):
        # Device connections: pairing_token → WebSocket
        self._device_connections: dict[str, WebSocket] = {}
        # Admin connections: user_id → set of WebSockets
        self._admin_connections: dict[str, set[WebSocket]] = {}
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

    async def register_admin(self, ws: WebSocket, user_id: str = ""):
        await ws.accept()
        self._admin_connections.setdefault(user_id, set()).add(ws)

    def unregister_admin(self, ws: WebSocket):
        for user_id, wss in list(self._admin_connections.items()):
            wss.discard(ws)
            if not wss:
                del self._admin_connections[user_id]

    async def broadcast_to_admins(self, data: dict, user_ids: list[str] = None):
        """Broadcast event to admin clients. If user_ids given, only to those users."""
        dead = []
        items = self._admin_connections.items()
        for user_id, wss in items:
            if user_ids is not None and user_id not in user_ids:
                continue
            for ws in list(wss):
                try:
                    await ws.send_json(data)
                except Exception:
                    dead.append((user_id, ws))
        for user_id, ws in dead:
            wss = self._admin_connections.get(user_id)
            if wss:
                wss.discard(ws)
                if not wss:
                    del self._admin_connections[user_id]

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
        """Register a device's persistent status connection.
        Caller must have already accepted the WebSocket before calling this.
        """
        # 先替换再关旧连接：旧连接的 finally 块检查时会发现已不是活跃连接，跳过离线标记
        old = self._device_status_connections.get(device_id)
        self._device_status_connections[device_id] = ws
        if old:
            try:
                await old.close()
            except Exception:
                pass

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
