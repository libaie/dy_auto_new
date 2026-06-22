"""设备运营业务域模块。

设备运营业务域，负责设备接入、脚本下发、轮询上报和状态生命周期。本文件负责 device_service 相关业务规则、状态转换和外部系统边界。
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.config import bj_now

from app.db.models.device_operations import Device


class DeviceService:
    """业务类：承载 DeviceService 相关的数据结构、状态或业务协作。

    类参数：无显式类参数 承载该类的业务配置、状态或数据字段。
    """
    def register(
        self, db: Session, device_id: str, name: str,
        os_version: str = "", app_version: str = "",
        ip: str = "",
        screen_resolution: str = "", sdk_version: str = "",
        total_memory: int = None,
        manufacturer: str = "", product: str = "",
        device_model: str = "", hardware: str = "", display: str = "",
    ) -> dict:
        """业务函数：处理 register 对应的业务流程、校验或数据转换。

        入参：db、device_id、name、os_version、app_version、ip、screen_resolution、sdk_version、total_memory、manufacturer、product、device_model、hardware、display 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
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
        """业务函数：处理 update_heartbeat 对应的业务流程、校验或数据转换。

        入参：db、device_id、ip 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
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
        """业务函数：处理 get_device_status 对应的业务流程、校验或数据转换。

        入参：db、device_id 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
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
        """业务函数：处理 set_offline_devices 对应的业务流程、校验或数据转换。

        入参：db、timeout_seconds 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
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
