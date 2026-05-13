"""Device management CRUD API."""
from fastapi import APIRouter, HTTPException, Depends, Query, WebSocket
from typing import Optional, Any
from pydantic import BaseModel
from sqlalchemy.orm import Session
import asyncio

from app.database import get_db
from app.db_models import Device, DevicePairRequest
from app.deps import verify_admin_token, verify_ws_admin_token
from app.ws_manager import pair_ws_manager

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.websocket("/ws/pair-events")
async def ws_pair_events(websocket: WebSocket, token: str = Query(...)):
    """Admin subscribes to real-time pairing events (new requests, approvals, rejections)."""
    username = verify_ws_admin_token(token)
    if not username:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await pair_ws_manager.register_admin(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        pair_ws_manager.unregister_admin(websocket)


class DeviceCreateRequest(BaseModel):
    name: str
    ip: Optional[str] = None
    bound_account_id: Optional[str] = None
    proxy_config: Optional[dict[str, Any]] = None


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
        "os_version": dev.os_version,
        "app_version": dev.app_version,
        "screen_resolution": dev.screen_resolution,
        "sdk_version": dev.sdk_version,
        "total_memory": dev.total_memory,
        "manufacturer": dev.manufacturer,
        "product": dev.product,
        "device_model": dev.device_model,
        "hardware": dev.hardware,
        "display": dev.display,
        "bound_account_id": dev.bound_account_id,
        "proxy_config": dev.proxy_config,
        "last_seen_at": str(dev.last_seen_at) if dev.last_seen_at else None,
        "created_at": str(dev.created_at) if dev.created_at else None,
        "updated_at": str(dev.updated_at) if dev.updated_at else None,
    }


@router.post("")
async def create_device(
    request: DeviceCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    # Validate bound_account_id references an existing account
    if request.bound_account_id:
        from app.db_models import Account
        if not db.query(Account).filter(Account.id == request.bound_account_id).first():
            raise HTTPException(status_code=404, detail="Account not found")

    dev = Device(
        name=request.name,
        ip=request.ip,
        bound_account_id=request.bound_account_id,
        proxy_config=request.proxy_config,
    )
    db.add(dev)
    db.commit()
    db.refresh(dev)
    await pair_ws_manager.broadcast_to_admins({"event": "devices_changed"})
    return _device_to_dict(dev)


@router.get("")
def list_devices(
    skip: int = 0,
    limit: int = 50,
    bound_account_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(Device)
    if bound_account_id is not None:
        query = query.filter(Device.bound_account_id == bound_account_id)
    total = query.count()
    devices = query.order_by(Device.created_at.desc()).offset(skip).limit(limit).all()
    return {"devices": [_device_to_dict(d) for d in devices], "total": total}


# --- Pair request management (admin-facing) ---
# MUST be defined BEFORE /{device_id} routes to avoid path conflicts


@router.get("/pair-requests")
def list_pair_requests(
    status: str = Query("pending"),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    """List device pairing requests, filtered by status."""
    query = db.query(DevicePairRequest)
    if status != "all":
        query = query.filter(DevicePairRequest.status == status)
    requests = query.order_by(DevicePairRequest.created_at.desc()).all()
    return {
        "requests": [
            {
                "id": r.id,
                "device_id": r.device_id,
                "device_name": r.device_name,
                "os_version": r.os_version,
                "app_version": r.app_version,
                "screen_resolution": r.screen_resolution,
                "sdk_version": r.sdk_version,
                "total_memory": r.total_memory,
                "manufacturer": r.manufacturer,
                "product": r.product,
                "device_model": r.device_model,
                "hardware": r.hardware,
                "display": r.display,
                "status": r.status,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in requests
        ],
        "total": len(requests),
    }


@router.post("/pair-requests/{request_id}/approve")
async def approve_pair_request(
    request_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    """Approve a pairing request — generates per-device secret and creates Device record."""
    import uuid
    from app.config import DEVICE_CONFIG, ANTI_DETECT_CONFIG, ANTI_DETECT_CONFIG_VERSION, get_ai_config

    pair_req = db.query(DevicePairRequest).filter(DevicePairRequest.id == request_id).first()
    if not pair_req:
        raise HTTPException(status_code=404, detail="Pair request not found")
    if pair_req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request already {pair_req.status}")

    # Generate per-device secret
    device_secret = uuid.uuid4().hex

    # Create or update Device record
    device = db.query(Device).filter(Device.id == pair_req.device_id).first()
    if device:
        device.device_secret = device_secret
        device.name = pair_req.device_name
        device.os_version = pair_req.os_version or device.os_version
        device.app_version = pair_req.app_version or device.app_version
        device.screen_resolution = pair_req.screen_resolution or device.screen_resolution
        device.sdk_version = pair_req.sdk_version or device.sdk_version
        device.total_memory = pair_req.total_memory or device.total_memory
        device.manufacturer = pair_req.manufacturer or device.manufacturer
        device.product = pair_req.product or device.product
        device.device_model = pair_req.device_model or device.device_model
        device.hardware = pair_req.hardware or device.hardware
        device.display = pair_req.display or device.display
    else:
        device = Device(
            id=pair_req.device_id,
            name=pair_req.device_name,
            os_version=pair_req.os_version,
            app_version=pair_req.app_version,
            screen_resolution=pair_req.screen_resolution,
            sdk_version=pair_req.sdk_version,
            total_memory=pair_req.total_memory,
            manufacturer=pair_req.manufacturer,
            product=pair_req.product,
            device_model=pair_req.device_model,
            hardware=pair_req.hardware,
            display=pair_req.display,
            device_secret=device_secret,
            status="offline",
        )
        db.add(device)

    # Update pair request
    pair_req.status = "approved"
    pair_req.device_secret = device_secret

    db.commit()

    # Push result to device via WebSocket (if connected)
    config = {
        **DEVICE_CONFIG,
        "anti_detect_config": ANTI_DETECT_CONFIG,
        "anti_detect_config_version": ANTI_DETECT_CONFIG_VERSION,
    }
    ai_cfg = get_ai_config(db)
    if ai_cfg:
        config["ai_config"] = ai_cfg
    await pair_ws_manager.notify(pair_req.pairing_token, {
        "status": "approved",
        "secret": device_secret,
        "config": config,
    })

    # Broadcast to admin clients
    await pair_ws_manager.broadcast_to_admins({
        "event": "pair_approved",
        "request_id": request_id,
        "device_id": pair_req.device_id,
    })

    return {"status": "approved", "device_id": pair_req.device_id}


@router.post("/pair-requests/{request_id}/reject")
async def reject_pair_request(
    request_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    """Reject a pairing request."""
    pair_req = db.query(DevicePairRequest).filter(DevicePairRequest.id == request_id).first()
    if not pair_req:
        raise HTTPException(status_code=404, detail="Pair request not found")
    if pair_req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request already {pair_req.status}")

    pair_req.status = "rejected"
    db.commit()

    # Push result to device via WebSocket (if connected)
    await pair_ws_manager.notify(pair_req.pairing_token, {
        "status": "rejected",
    })

    # Broadcast to admin clients
    await pair_ws_manager.broadcast_to_admins({
        "event": "pair_rejected",
        "request_id": request_id,
        "device_id": pair_req.device_id,
    })

    return {"status": "rejected"}


@router.get("/{device_id}")
def get_device(
    device_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    return _device_to_dict(dev)


@router.put("/{device_id}")
async def update_device(
    device_id: str,
    request: DeviceUpdateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")

    config_changed = False
    proxy_changed = False

    if request.name is not None:
        dev.name = request.name
    if request.ip is not None:
        dev.ip = request.ip
    if request.status is not None:
        dev.status = request.status
    if request.bound_account_id is not None:
        if request.bound_account_id:
            from app.db_models import Account
            if not db.query(Account).filter(Account.id == request.bound_account_id).first():
                raise HTTPException(status_code=404, detail="Account not found")
        dev.bound_account_id = request.bound_account_id
    if request.proxy_config is not None:
        dev.proxy_config = request.proxy_config
        proxy_changed = True

    db.commit()
    db.refresh(dev)

    # Push config/proxy changes to device via WS
    if proxy_changed:
        await pair_ws_manager.send_to_device(device_id, {
            "event": "config_updated",
            "proxy": dev.proxy_config,
        })

    await pair_ws_manager.broadcast_to_admins({"event": "devices_changed"})
    return _device_to_dict(dev)


@router.post("/{device_id}/disconnect")
async def disconnect_device(
    device_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    """Force-disconnect a device by closing its WebSocket connection.

    The device will detect the disconnect, attempt to reconnect, and
    the server will mark it offline in the database.
    """
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")

    closed = await pair_ws_manager.disconnect_device(device_id)
    if not closed:
        return {"status": "not_connected", "device_id": device_id, "detail": "设备当前无活跃连接"}

    dev.status = "offline"
    db.commit()

    # Broadcast status change to admins
    await pair_ws_manager.broadcast_to_admins({
        "event": "device_status_changed",
        "device_id": device_id,
        "status": "offline",
    })

    return {"status": "disconnected", "device_id": device_id}


@router.delete("/{device_id}")
async def delete_device(
    device_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    from app.db_models import Task, DevicePairRequest

    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")

    # 1. 通知设备：你已被移除
    await pair_ws_manager.send_to_device(device_id, {
        "event": "device_removed",
    })
    # 2. 关闭设备 WS 连接
    await pair_ws_manager.disconnect_device(device_id)

    # 3. 解绑该设备上的待执行任务（放回队列等待其他设备领取）
    db.query(Task).filter(
        Task.device_id == device_id,
        Task.status.in_(["pending", "running"]),
    ).update({"device_id": None, "status": "pending", "started_at": None}, synchronize_session=False)

    # 4. 删除配对请求记录
    db.query(DevicePairRequest).filter(DevicePairRequest.device_id == device_id).delete()

    # 5. 删除设备
    db.delete(dev)
    db.commit()

    # 6. 通知前端
    await pair_ws_manager.broadcast_to_admins({
        "event": "device_status_changed",
        "device_id": device_id,
        "status": "deleted",
    })

    return {"deleted": True, "id": device_id}
