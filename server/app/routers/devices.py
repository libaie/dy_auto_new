"""Device management CRUD API."""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, Any
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import Device
from app.deps import verify_device_secret

router = APIRouter(prefix="/api/devices", tags=["devices"])


class DeviceCreateRequest(BaseModel):
    name: str
    ip: Optional[str] = None
    bound_account_id: Optional[str] = None


class DeviceUpdateRequest(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    status: Optional[str] = None
    bound_account_id: Optional[str] = None
    proxy_config: Optional[dict[str, Any]] = None


def _device_to_dict(dev: Device) -> dict:
    return {
        "id": dev.id,
        "name": dev.name,
        "ip": dev.ip,
        "status": dev.status,
        "bound_account_id": dev.bound_account_id,
        "proxy_config": dev.proxy_config,
        "last_seen_at": str(dev.last_seen_at) if dev.last_seen_at else None,
        "created_at": str(dev.created_at) if dev.created_at else None,
        "updated_at": str(dev.updated_at) if dev.updated_at else None,
    }


@router.post("")
def create_device(
    request: DeviceCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    dev = Device(
        name=request.name,
        ip=request.ip,
        bound_account_id=request.bound_account_id,
    )
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return _device_to_dict(dev)


@router.get("")
def list_devices(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    total = db.query(Device).count()
    devices = db.query(Device).order_by(Device.created_at.desc()).offset(skip).limit(limit).all()
    return {"devices": [_device_to_dict(d) for d in devices], "total": total}


@router.get("/{device_id}")
def get_device(
    device_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    return _device_to_dict(dev)


@router.put("/{device_id}")
def update_device(
    device_id: str,
    request: DeviceUpdateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")

    if request.name is not None:
        dev.name = request.name
    if request.ip is not None:
        dev.ip = request.ip
    if request.status is not None:
        dev.status = request.status
    if request.bound_account_id is not None:
        dev.bound_account_id = request.bound_account_id
    if request.proxy_config is not None:
        dev.proxy_config = request.proxy_config

    db.commit()
    db.refresh(dev)
    return _device_to_dict(dev)


@router.delete("/{device_id}")
def delete_device(
    device_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(dev)
    db.commit()
    return {"deleted": True, "id": device_id}
