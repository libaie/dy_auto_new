"""Device-facing API — poll, report, heartbeat, selectors."""
from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File as FastAPIFile, WebSocket, Request
from typing import Optional
from sqlalchemy.orm import Session
import asyncio
import io

from app.models import TaskResultReport, PollResponse, DeviceRegisterRequest, DeviceRegisterResponse, RiskReport, DeviceGenerateRequest, DeviceGenerateResponse, DeviceAIProxyRequest, DeviceAIProxyResponse, PairRequestCreate, PairStatusResponse
from app.database import get_db
from app.deps import verify_device_secret, verify_admin_token
from app.services.task_service import task_service
from app.config import ANTI_DETECT_CONFIG, ANTI_DETECT_CONFIG_VERSION, DEVICE_CONFIG
from app.services.selector_service import selector_service
from app.ws_manager import pair_ws_manager

router = APIRouter(prefix="/api/device", tags=["device"])


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
    from app.db_models import DevicePairRequest, Device

    # Capture client IP (prefer X-Forwarded-For for reverse proxy setups)
    client_ip = raw_request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip:
        client_ip = raw_request.client.host if raw_request.client else ""

    # 1. Already paired — Device exists with a valid secret
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
        # Return full approved payload (secret + config) so device can reconnect immediately
        class _FakePairReq:
            device_secret = device.device_secret
        payload = _build_approved_payload(_FakePairReq())
        return PairStatusResponse(**payload)

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
    from app.db_models import DevicePairRequest, Device

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
    from app.db_models import DevicePairRequest, Device

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


@router.websocket("/ws/status")
async def ws_device_status(websocket: WebSocket, device_id: str = Query(""), secret: str = Query("")):
    """Device maintains a persistent WS connection for status tracking.
    Server detects disconnect immediately → marks device offline → broadcasts to admins.
    """
    from app.db_models import Device
    from app.config import DEVICE_SECRET

    # Authenticate: accept master secret or per-device secret
    if not secret:
        await websocket.accept()
        await websocket.close(code=4001, reason="Missing secret")
        return

    db = next(get_db())
    try:
        if secret != DEVICE_SECRET:
            device = db.query(Device).filter(Device.device_secret == secret).first()
            if not device:
                await websocket.accept()
                await websocket.close(code=4001, reason="Invalid secret")
                return
            device_id = device.id

        if not device_id:
            await websocket.accept()
            await websocket.close(code=4001, reason="Missing device_id")
            return

        # Mark device online and capture IP
        from app.services.device_service import device_service
        ws_client_ip = websocket.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not ws_client_ip:
            ws_client_ip = websocket.client.host if websocket.client else ""
        device_service.update_heartbeat(db, device_id, ip=ws_client_ip)
        await pair_ws_manager.broadcast_to_admins({
            "event": "device_status_changed",
            "device_id": device_id,
            "status": "online",
        })

        # Register connection
        await pair_ws_manager.register_device_status(device_id, websocket)

        try:
            while True:
                # Keep alive — wait for client messages (text ping/close)
                # OkHttp protocol-level pings may not be seen by Starlette,
                # so we use a longer timeout and rely on device-side app-level pings
                try:
                    msg = await asyncio.wait_for(websocket.receive_text(), timeout=120)
                    # Device explicitly disconnecting (script shutdown)
                    if msg == '{"event":"device_disconnect"}':
                        break
                    # Echo back as acknowledgment (device can ignore)
                    if msg == "ping":
                        await websocket.send_text("pong")
                except asyncio.TimeoutError:
                    # No message for 120s — send a server-side ping to probe liveness
                    try:
                        await websocket.send_text("ping")
                        msg = await asyncio.wait_for(websocket.receive_text(), timeout=10)
                    except (asyncio.TimeoutError, Exception):
                        # Device is unresponsive, close connection
                        break
        except (asyncio.TimeoutError, Exception):
            pass
        finally:
            # Device disconnected → mark offline immediately
            pair_ws_manager.unregister_device_status(device_id)
            db2 = next(get_db())
            try:
                device_obj = db2.query(Device).filter(Device.id == device_id).first()
                if device_obj:
                    device_obj.status = "offline"
                    db2.commit()
            finally:
                db2.close()
            await pair_ws_manager.broadcast_to_admins({
                "event": "device_status_changed",
                "device_id": device_id,
                "status": "offline",
            })
    finally:
        db.close()


@router.get("/poll", response_model=PollResponse)
def poll_tasks(
    device_id: str = Query(...),
    db: Session = Depends(get_db),
    authed_device_id: Optional[str] = Depends(verify_device_secret),
):
    # Per-device secret: use the verified device_id, reject mismatch
    if authed_device_id and authed_device_id != device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")
    if authed_device_id:
        device_id = authed_device_id

    task = task_service.get_pending_task(db, device_id)
    version = selector_service.get_version(db)

    from app.services.device_service import device_service
    device_info = device_service.get_device_status(db, device_id)
    proxy = device_info.get("proxy_config") if device_info else None

    cancelled_task = task_service.check_cancelled_running(db, device_id)

    from app.config import get_ai_config

    return PollResponse(
        task=task,
        selectors_version=version,
        proxy=proxy,
        cancelled_task_id=cancelled_task.id if cancelled_task else None,
        anti_detect_config=ANTI_DETECT_CONFIG,
        anti_detect_config_version=ANTI_DETECT_CONFIG_VERSION,
        ai_config=get_ai_config(db),
        device_config=DEVICE_CONFIG,
    )


@router.post("/report")
def report_result(
    report: TaskResultReport,
    db: Session = Depends(get_db),
    authed_device_id: Optional[str] = Depends(verify_device_secret),
):
    # Per-device secret: verify the task belongs to this device
    if authed_device_id:
        from app.db_models import Task as DBTask
        db_task = db.query(DBTask).filter(DBTask.id == report.task_id).first()
        if not db_task:
            raise HTTPException(status_code=404, detail="Task not found")
        if db_task.device_id and db_task.device_id != authed_device_id:
            raise HTTPException(status_code=403, detail="Task does not belong to this device")

    try:
        task = task_service.report_result(
            db=db,
            task_id=report.task_id,
            status=report.status,
            result=report.result,
            ui_snapshot=report.ui_snapshot,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/heartbeat")
async def heartbeat(
    body: dict,
    raw_request: Request,
    db: Session = Depends(get_db),
    authed_device_id: Optional[str] = Depends(verify_device_secret),
):
    device_id = body.get("device_id", "")
    # Per-device secret: use the verified device_id, reject mismatch
    if authed_device_id and authed_device_id != device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")
    if authed_device_id:
        device_id = authed_device_id

    client_ip = raw_request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip:
        client_ip = raw_request.client.host if raw_request.client else ""
    from app.services.device_service import device_service
    status_changed = device_service.update_heartbeat(db, device_id, ip=client_ip)
    if status_changed:
        await pair_ws_manager.broadcast_to_admins({
            "event": "device_status_changed",
            "device_id": device_id,
            "status": "online",
        })
    return {"status": "ok", "device_id": device_id}


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
    from app.services.device_service import device_service
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


@router.get("/selectors")
def get_selectors(
    version: int = Query(0),
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):

    current_version, selectors = selector_service.get_all_selectors(db)
    if version == current_version:
        return {"version": current_version, "selectors": None, "changed": False}

    return {
        "version": current_version,
        "selectors": selectors,
        "changed": True,
    }


@router.get("/script-version")
def script_version(
    _: None = Depends(verify_device_secret),
):
    from app.services.script_service import script_service
    return {"version": script_service.get_version()}


@router.get("/script-download")
def script_download(
    _: None = Depends(verify_device_secret),
):
    from app.services.script_service import script_service
    from fastapi.responses import Response
    data = script_service.download_script()
    if data is None:
        raise HTTPException(status_code=404, detail="No script available")
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=device-script.zip"},
    )


@router.post("/script-upload")
async def script_upload(
    file: UploadFile = FastAPIFile(...),
    _: str = Depends(verify_admin_token),
):
    from app.services.script_service import script_service
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files accepted")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    new_version = script_service.upload_script(io.BytesIO(content))
    return {"version": new_version, "size": len(content)}


@router.post("/risk-report")
def report_risk(
    report: RiskReport,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    """Device reports risk control detection. Marks account as risk_controlled."""
    from app.db_models import Account
    account = db.query(Account).filter(Account.id == report.account_id).first()
    if not account:
        return {"status": "ignored", "account_status": "unknown"}
    if account.status == "active":
        account.status = "risk_controlled"
        db.commit()
    return {"status": "acknowledged", "account_status": account.status}


@router.post("/generate-content", response_model=DeviceGenerateResponse)
async def generate_content(
    request: DeviceGenerateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    """Generate content from a template on-demand."""
    from app.services.content_service import content_service

    try:
        content = await content_service.generate_from_template(
            db, request.template_id, request.context,
        )
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail="Template not found")
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")

    return DeviceGenerateResponse(content=content, template_id=request.template_id)


@router.post("/ai-proxy", response_model=DeviceAIProxyResponse)
async def ai_proxy(
    request: DeviceAIProxyRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    """设备端 AI 代理 — 设备不持有 API Key，通过服务端调用 AI。"""
    import httpx
    from app.config import get_ai_config_with_key

    ai_cfg = get_ai_config_with_key(db)
    if not ai_cfg or not ai_cfg.get("api_url"):
        raise HTTPException(status_code=503, detail="AI service not configured")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                ai_cfg["api_url"],
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {ai_cfg.get('api_key', '')}",
                },
                json={
                    "model": ai_cfg.get("model", "deepseek-chat"),
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                    "messages": [{"role": "user", "content": request.prompt}],
                },
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"AI API error: {resp.status_code}")
        result = resp.json()
        content = result["choices"][0]["message"]["content"].strip()
        return DeviceAIProxyResponse(content=content)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI API timeout")
    except (KeyError, IndexError) as e:
        raise HTTPException(status_code=502, detail=f"Invalid AI response: {e}")
