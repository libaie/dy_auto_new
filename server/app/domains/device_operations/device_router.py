"""Device-facing API — poll, report, heartbeat, selectors."""
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional
from sqlalchemy.orm import Session

from app.models import (
    DeviceRegisterRequest,
    DeviceRegisterResponse,
)
from app.database import get_db
from app.deps import verify_device_secret
from app.config import ANTI_DETECT_CONFIG, ANTI_DETECT_CONFIG_VERSION, DEVICE_CONFIG
from app.domains.device_operations import content_bridge, pairing, polling, reporting, script_assets, status_ws

router = APIRouter(prefix="/api/device", tags=["device"])

router.include_router(pairing.router)
router.include_router(status_ws.router)

router.include_router(polling.router)
router.include_router(reporting.router)


@router.post("/register", response_model=DeviceRegisterResponse)
def register_device(
    request: DeviceRegisterRequest,
    raw_request: Request,
    db: Session = Depends(get_db),
    authed_device_id: Optional[str] = Depends(verify_device_secret),
):
    # Per-device secret: reject mismatch
    if authed_device_id and authed_device_id != request.device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")
    from app.domains.device_operations.device_service import device_service
    from app.config import get_ai_config

    # Capture client IP
    client_ip = raw_request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip:
        client_ip = raw_request.client.host if raw_request.client else ""

    result = device_service.register(
        db=db, device_id=request.device_id, name=request.name,
        os_version=request.os_version, app_version=request.app_version,
        ip=client_ip,
        screen_resolution=request.screen_resolution,
        sdk_version=request.sdk_version,
        total_memory=request.total_memory,
        manufacturer=request.manufacturer,
        product=request.product,
        device_model=request.device_model,
        hardware=request.hardware,
        display=request.display,
    )

    # 组装完整设备配置
    config = {
        **DEVICE_CONFIG,
        "anti_detect_config": ANTI_DETECT_CONFIG,
        "anti_detect_config_version": ANTI_DETECT_CONFIG_VERSION,
    }
    ai_cfg = get_ai_config(db)
    if ai_cfg:
        config["ai_config"] = ai_cfg

    return DeviceRegisterResponse(
        device_id=result["device_id"],
        name=result["name"],
        status=result["status"],
        config=config,
    )


router.include_router(script_assets.router)
router.include_router(reporting.risk_router)
router.include_router(content_bridge.pre_template_router)
router.include_router(script_assets.template_router)
router.include_router(content_bridge.router)
