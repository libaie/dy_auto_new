"""Device pairing routes."""
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PairRequestCreate, PairStatusResponse
from app.ws_manager import pair_ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()
# In-memory rate limiter for unauthenticated endpoints (pair-request)
_pair_rate_limits: dict[str, list] = {}  # IP → [timestamps]

@router.post("/pair-request", response_model=PairStatusResponse)
async def create_pair_request(
    request: PairRequestCreate,
    raw_request: Request,
    db: Session = Depends(get_db),
):
    """Unauthenticated — device sends pairing request to server.

    Flow:
    1. Device already has a valid secret → return "approved" (reconnect)
    2. Pending request exists → return same token (don't duplicate)
    3. Otherwise → clean old rejected, create new pending, notify admins
    """
    import uuid
    from app.db.models.device_operations import Device, DevicePairRequest

    # Capture client IP (prefer X-Forwarded-For for reverse proxy setups)
    client_ip = raw_request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip:
        client_ip = raw_request.client.host if raw_request.client else ""

    # Rate limit: max 5 pair requests per hour per IP
    import time as _time
    now_ts = _time.time()
    window = now_ts - 3600
    _pair_rate_limits.setdefault(client_ip, [])
    _pair_rate_limits[client_ip] = [t for t in _pair_rate_limits[client_ip] if t > window]
    if not _pair_rate_limits[client_ip]:
        _pair_rate_limits.pop(client_ip, None)  # prevent memory leak: clean empty entries
    elif len(_pair_rate_limits[client_ip]) >= 5:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    _pair_rate_limits.setdefault(client_ip, []).append(now_ts)

    # 1. Already paired — Device exists with a valid secret
    # SECURITY: Do NOT auto-return secret. If the device lost its local config,
    # create a new pending request so admin must re-approve.
    device = db.query(Device).filter(Device.id == request.device_id).first()
    if device and device.device_secret:
        # Update IP and device info on reconnect
        device.ip = client_ip or device.ip
        device.screen_resolution = request.screen_resolution or device.screen_resolution
        device.sdk_version = request.sdk_version or device.sdk_version
        device.total_memory = request.total_memory or device.total_memory
        device.manufacturer = request.manufacturer or device.manufacturer
        device.product = request.product or device.product
        device.device_model = request.device_model or device.device_model
        device.hardware = request.hardware or device.hardware
        device.display = request.display or device.display
        db.commit()
        # Create a new pending pair request — admin must re-approve
        # to disclose the secret. Don't auto-return it.
        logger.warning(
            "Already-paired device %s re-requested pairing (secret not disclosed). "
            "Creating pending request for admin re-approval.",
            request.device_id,
        )
        # Fall through to pending/new request logic below

    # 2. Pending request already exists — return same token
    pending = db.query(DevicePairRequest).filter(
        DevicePairRequest.device_id == request.device_id,
        DevicePairRequest.status == "pending",
    ).first()
    if pending:
        # Update IP and device info on re-request
        device = db.query(Device).filter(Device.id == request.device_id).first()
        if device:
            device.ip = client_ip or device.ip
            db.commit()
        return PairStatusResponse(pairing_token=pending.pairing_token, status="pending")

    # 3. Clean old rejected requests for this device (allow re-pairing)
    db.query(DevicePairRequest).filter(
        DevicePairRequest.device_id == request.device_id,
        DevicePairRequest.status == "rejected",
    ).delete()
    db.commit()

    # 4. Create new pair request with enriched device info
    token = uuid.uuid4().hex
    pair_req = DevicePairRequest(
        pairing_token=token,
        device_id=request.device_id,
        device_name=request.device_name,
        os_version=request.os_version,
        app_version=request.app_version,
        screen_resolution=request.screen_resolution,
        sdk_version=request.sdk_version,
        total_memory=request.total_memory,
        manufacturer=request.manufacturer,
        product=request.product,
        device_model=request.device_model,
        hardware=request.hardware,
        display=request.display,
        status="pending",
    )
    db.add(pair_req)

    # Also create/update Device record with IP
    device = db.query(Device).filter(Device.id == request.device_id).first()
    if device:
        device.ip = client_ip or device.ip
    else:
        device = Device(
            id=request.device_id,
            name=request.device_name,
            ip=client_ip,
            os_version=request.os_version,
            app_version=request.app_version,
            status="offline",
        )
        db.add(device)

    db.commit()
    db.refresh(pair_req)

    # 5. Broadcast to admin clients
    await pair_ws_manager.broadcast_to_admins({
        "event": "new_pair_request",
        "request": {
            "id": pair_req.id,
            "device_id": pair_req.device_id,
            "device_name": pair_req.device_name,
            "os_version": pair_req.os_version,
            "app_version": pair_req.app_version,
            "screen_resolution": pair_req.screen_resolution,
            "sdk_version": pair_req.sdk_version,
            "total_memory": pair_req.total_memory,
            "manufacturer": pair_req.manufacturer,
            "product": pair_req.product,
            "device_model": pair_req.device_model,
            "hardware": pair_req.hardware,
            "display": pair_req.display,
            "status": pair_req.status,
            "ip": client_ip,
            "created_at": str(pair_req.created_at),
        },
    })

    return PairStatusResponse(pairing_token=token, status="pending")


def _build_approved_payload(pair_req, db=None) -> dict:
    """Build the approved response payload (shared by HTTP and WS)."""
    from app.config import DEVICE_CONFIG, ANTI_DETECT_CONFIG, ANTI_DETECT_CONFIG_VERSION, get_ai_config

    config = {
        **DEVICE_CONFIG,
        "anti_detect_config": ANTI_DETECT_CONFIG,
        "anti_detect_config_version": ANTI_DETECT_CONFIG_VERSION,
    }
    ai_cfg = get_ai_config(db)
    if ai_cfg:
        config["ai_config"] = ai_cfg

    return {
        "status": "approved",
        "secret": pair_req.device_secret,
        "config": config,
    }


@router.get("/pair-status", response_model=PairStatusResponse)
def check_pair_status(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """Unauthenticated — device polls for approval result."""
    from app.db.models.device_operations import Device, DevicePairRequest

    pair_req = db.query(DevicePairRequest).filter(
        DevicePairRequest.pairing_token == token,
    ).first()

    if not pair_req:
        raise HTTPException(status_code=404, detail="Pairing request not found")

    if pair_req.status == "pending":
        return PairStatusResponse(status="pending")

    if pair_req.status == "rejected":
        return PairStatusResponse(status="rejected")

    # Approved — verify Device still exists with matching secret
    device = db.query(Device).filter(Device.id == pair_req.device_id).first()
    if not device or device.device_secret != pair_req.device_secret:
        # Device was deleted or secret changed — need re-approval
        return PairStatusResponse(status="pending")

    payload = _build_approved_payload(pair_req)
    return PairStatusResponse(**payload)


@router.websocket("/ws/pair/{token}")
async def ws_pair_status(websocket: WebSocket, token: str):
    """Device connects via WS to receive real-time pairing approval result."""
    from app.db.models.device_operations import Device, DevicePairRequest

    db = next(get_db())
    try:
        pair_req = db.query(DevicePairRequest).filter(
            DevicePairRequest.pairing_token == token,
        ).first()

        if not pair_req:
            await websocket.close(code=4004, reason="Invalid token")
            return

        # Already resolved — send result immediately and close
        if pair_req.status == "approved":
            # Verify Device still exists with matching secret
            device = db.query(Device).filter(Device.id == pair_req.device_id).first()
            if device and device.device_secret == pair_req.device_secret:
                await websocket.accept()
                await websocket.send_json(_build_approved_payload(pair_req))
                await websocket.close()
                return
            # Device deleted or secret changed — treat as pending (wait for re-approval)
            pair_req.status = "pending"
            db.commit()
        elif pair_req.status == "rejected":
            await websocket.accept()
            await websocket.send_json({"status": "rejected"})
            await websocket.close()
            return

        # pending — register connection, wait for admin action
        await pair_ws_manager.register(token, websocket)

        try:
            while True:
                # Keep connection alive; timeout after 5 minutes
                await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=300,
                )
        except (asyncio.TimeoutError, Exception):
            pass
        finally:
            pair_ws_manager.unregister(token)
    finally:
        db.close()
