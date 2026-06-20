"""Device registration, heartbeat, and status management for device operations."""
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.config import bj_now

from app.db_models import Device


class DeviceService:
    def register(
        self, db: Session, device_id: str, name: str,
        os_version: str = "", app_version: str = "",
        ip: str = "",
        screen_resolution: str = "", sdk_version: str = "",
        total_memory: int = None,
        manufacturer: str = "", product: str = "",
        device_model: str = "", hardware: str = "", display: str = "",
    ) -> dict:
        """Register or update a device. Returns device info dict."""
        device = db.query(Device).filter(Device.id == device_id).first()
        now = bj_now()

        if device:
            device.name = name
            device.os_version = os_version
            device.app_version = app_version
            if ip:
                device.ip = ip
            device.screen_resolution = screen_resolution or device.screen_resolution
            device.sdk_version = sdk_version or device.sdk_version
            device.total_memory = total_memory or device.total_memory
            device.manufacturer = manufacturer or device.manufacturer
            device.product = product or device.product
            device.device_model = device_model or device.device_model
            device.hardware = hardware or device.hardware
            device.display = display or device.display
            device.status = "online"
            device.last_seen_at = now
        else:
            device = Device(
                id=device_id, name=name, os_version=os_version, app_version=app_version,
                ip=ip or None,
                screen_resolution=screen_resolution, sdk_version=sdk_version,
                total_memory=total_memory, manufacturer=manufacturer, product=product,
                device_model=device_model, hardware=hardware, display=display,
                status="online", last_seen_at=now,
            )
            db.add(device)

        db.commit()
        db.refresh(device)

        return {
            "device_id": device.id,
            "name": device.name,
            "os_version": device.os_version,
            "app_version": device.app_version,
            "status": device.status,
        }

    def update_heartbeat(self, db: Session, device_id: str, ip: str = "") -> bool:
        """Update device last_seen_at. Returns True if status changed to online."""
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            return False
        was_offline = device.status != "online"
        device.last_seen_at = bj_now()
        device.status = "online"
        if ip:
            device.ip = ip
        db.commit()
        return was_offline

    def get_device_status(self, db: Session, device_id: str) -> dict | None:
        """Get device status info including proxy_config. Returns None for unknown devices."""
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            return None
        return {
            "device_id": device.id,
            "name": device.name,
            "status": device.status,
            "os_version": device.os_version,
            "app_version": device.app_version,
            "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
            "proxy_config": device.proxy_config,
        }

    def set_offline_devices(self, db: Session, timeout_seconds: int = 300) -> int:
        """Mark devices as offline if no heartbeat for timeout_seconds. Returns count."""
        now = bj_now()
        cutoff_dt = now - timedelta(seconds=timeout_seconds)
        count = (
            db.query(Device)
            .filter(Device.status == "online", Device.last_seen_at < cutoff_dt)
            .update({"status": "offline"})
        )
        db.commit()
        return count


device_service = DeviceService()
