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
        # Roles belong to connections, so simultaneous sessions remain isolated.
        self._admin_roles: dict[WebSocket, str] = {}
        # Device status connections: device_id → WebSocket
        self._device_status_connections: dict[str, WebSocket] = {}
        # Heartbeat memory cache: device_id → datetime
        self._device_last_seen: dict[str, object] = {}

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

    async def register_admin(self, ws: WebSocket, user_id: str = "", role: str = "admin"):
        await ws.accept()
        self._admin_connections.setdefault(user_id, set()).add(ws)
        self._admin_roles[ws] = role

    def unregister_admin(self, ws: WebSocket):
        self._admin_roles.pop(ws, None)
        for user_id, wss in list(self._admin_connections.items()):
            wss.discard(ws)
            if not wss:
                del self._admin_connections[user_id]

    async def broadcast_to_admins(self, data: dict, user_ids: list[str] = None):
        """Deliver to administrators and explicitly scoped resource owners only."""
        dead = []
        items = list(self._admin_connections.items())
        for user_id, wss in items:
            for ws in list(wss):
                if self._admin_roles.get(ws) != "admin" and (not user_id or user_ids is None or user_id not in user_ids):
                    continue
                try:
                    await ws.send_json(data)
                except Exception:
                    dead.append((user_id, ws))
        for user_id, ws in dead:
            self._admin_roles.pop(ws, None)
            wss = self._admin_connections.get(user_id)
            if wss:
                wss.discard(ws)
                if not wss:
                    del self._admin_connections[user_id]

    async def broadcast_invalidation(self, event: str):
        """Publish an intentional, payload-free refresh signal to all users.

        Keep this allowlist separate from confidential resource notifications.
        Callers cannot attach IDs, task results, or other per-user data.
        """
        allowed = {
            "accounts_changed", "account_groups_changed", "chains_changed",
            "content_changed", "selectors_changed", "prompt_templates_changed",
        }
        if not isinstance(event, str) or event not in allowed:
            raise ValueError("Unsupported global invalidation event")
        await self.broadcast_to_admins({"event": event}, user_ids=list(self._admin_connections))

    async def broadcast_channel_progress(self, channel_id: str, stats: dict, user_ids: list[str] = None):
        """Push channel progress event to admin WS connections."""
        await self.broadcast_to_admins({
            "event": "channel_progress",
            "channel_id": channel_id,
            **stats,
        }, user_ids=user_ids)

    async def broadcast_channel_completed(self, channel_id: str, user_ids: list[str] = None):
        """Push channel completed event to admin WS connections."""
        await self.broadcast_to_admins({
            "event": "channel_completed",
            "channel_id": channel_id,
        }, user_ids=user_ids)

    # --- Heartbeat memory cache (avoids DB write on every ping) ---

    def record_heartbeat(self, device_id: str, seen_at):
        """Record heartbeat in memory. Caller flushes to DB periodically."""
        self._device_last_seen[device_id] = seen_at

    def get_last_seen(self, device_id: str):
        """Get the in-memory last seen time, or None."""
        return self._device_last_seen.get(device_id)

    def drain_heartbeats(self) -> dict[str, object]:
        """Atomically swap out all in-memory heartbeats for DB flush."""
        heartbeats = self._device_last_seen
        self._device_last_seen = {}
        return heartbeats

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
