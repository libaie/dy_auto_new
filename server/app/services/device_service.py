"""Device registration, heartbeat, and status management."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db_models import Device


class DeviceService:
    def register(
        self, db: Session, device_id: str, name: str,
        os_version: str = "", app_version: str = "",
    ) -> dict:
        """Register or update a device. Returns device info dict."""
        device = db.query(Device).filter(Device.id == device_id).first()
        now = datetime.now(timezone.utc)

        if device:
            device.name = name
            device.status = "online"
            device.last_seen_at = now
        else:
            device = Device(id=device_id, name=name, status="online", last_seen_at=now)
            db.add(device)

        db.commit()
        db.refresh(device)

        return {
            "device_id": device.id,
            "name": device.name,
            "status": device.status,
        }

    def update_heartbeat(self, db: Session, device_id: str) -> None:
        """Update device last_seen_at. Ignores unknown devices."""
        device = db.query(Device).filter(Device.id == device_id).first()
        if device:
            device.last_seen_at = datetime.now(timezone.utc)
            device.status = "online"
            db.commit()

    def get_device_status(self, db: Session, device_id: str) -> dict | None:
        """Get device status info including proxy_config. Returns None for unknown devices."""
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            return None
        return {
            "device_id": device.id,
            "name": device.name,
            "status": device.status,
            "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
            "proxy_config": device.proxy_config,
        }

    def set_offline_devices(self, db: Session, timeout_seconds: int = 300) -> int:
        """Mark devices as offline if no heartbeat for timeout_seconds. Returns count."""
        cutoff = datetime.now(timezone.utc).timestamp() - timeout_seconds
        cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
        count = (
            db.query(Device)
            .filter(Device.status == "online", Device.last_seen_at < cutoff_dt)
            .update({"status": "offline"})
        )
        db.commit()
        return count


device_service = DeviceService()
