"""Device-facing API — poll, report, heartbeat, selectors."""
from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File as FastAPIFile, WebSocket, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
import asyncio
import io

from app.models import TaskProgressReport, TaskResultReport, PollResponse, DeviceRegisterRequest, DeviceRegisterResponse, RiskReport, DeviceGenerateRequest, DeviceGenerateResponse, DeviceAIProxyRequest, DeviceAIProxyResponse, PairRequestCreate, PairStatusResponse
from app.database import get_db
from app.deps import verify_device_secret, verify_admin_token
from app.services.task_service import task_service
from app.config import ANTI_DETECT_CONFIG, ANTI_DETECT_CONFIG_VERSION, DEVICE_CONFIG
from app.services.selector_service import selector_service
from app.services.prompt_template_service import prompt_template_service
from app.ws_manager import pair_ws_manager

router = APIRouter(prefix="/api/device", tags=["device"])


async def _notify_pending_tasks(db: Session, device_id: str):
    """Check if there are pending tasks for this device and notify it via WS."""
    import logging
    logger = logging.getLogger(__name__)

    from app.db_models import Device, Task as DBTask
    from app.models import TaskStatus
    from datetime import datetime, timezone
    from sqlalchemy import or_, and_

    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        logger.info(f"[notify] 设备 {device_id} 不存在，跳过")
        return

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Build routing filter (same logic as task_service.get_pending_task)
    if device.bound_account_id:
        route_filter = or_(
            DBTask.device_id == device_id,
            and_(DBTask.device_id.is_(None), DBTask.account_id == device.bound_account_id),
        )
        logger.info(f"[notify] 设备 {device_id} 绑定账号 {device.bound_account_id}，查询匹配任务...")
    else:
        bound_account_ids = db.query(Device.bound_account_id).filter(
            Device.bound_account_id.isnot(None)
        ).scalar_subquery()
        route_filter = or_(
            DBTask.device_id == device_id,
            and_(DBTask.device_id.is_(None), ~DBTask.account_id.in_(bound_account_ids)),
        )
        logger.info(f"[notify] 设备 {device_id} 未绑定账号，查询孤儿任务...")

    pending_tasks = db.query(DBTask).filter(
        DBTask.status == TaskStatus.PENDING.value,
        route_filter,
        or_(DBTask.scheduled_at.is_(None), DBTask.scheduled_at <= now),
    ).all()

    # Also check pending channel items for this device
    from app.db_models import ChannelItem, Channel
    channel_item_query = db.query(ChannelItem).filter(
        ChannelItem.status == "pending",
        ChannelItem.channel_id.in_(
            db.query(Channel.id).filter(Channel.status == "active", Channel.deleted_at.is_(None))
        ),
    )
    if device.bound_account_id:
        channel_item_query = channel_item_query.filter(ChannelItem.account_id == device.bound_account_id)
    pending_channel_count = channel_item_query.count()

    logger.info(f"[notify] 设备 {device_id} 找到 {len(pending_tasks)} 个待执行任务, {pending_channel_count} 个待分发通道项")

    if pending_tasks or pending_channel_count > 0:
        sent = await pair_ws_manager.send_to_device(device_id, {"event": "new_task_available"})
        logger.info(f"[notify] 向设备 {device_id} 推送 new_task_available: {'成功' if sent else '失败'}")


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

        # Register WS connection FIRST — before DB update — so _offline_checker
        # never sees "DB online but no WS" during the race window
        await pair_ws_manager.register_device_status(device_id, websocket)

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

        # Check for pending tasks and notify device
        await _notify_pending_tasks(db, device_id)

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
    tmpl_version = prompt_template_service.get_version(db)

    from app.services.device_service import device_service
    device_info = device_service.get_device_status(db, device_id)
    proxy = device_info.get("proxy_config") if device_info else None

    cancelled_task = task_service.check_cancelled_running(db, device_id)

    from app.config import get_ai_config

    return PollResponse(
        task=task,
        selectors_version=version,
        prompt_templates_version=tmpl_version,
        proxy=proxy,
        cancelled_task_id=cancelled_task.id if cancelled_task else None,
        anti_detect_config=ANTI_DETECT_CONFIG,
        anti_detect_config_version=ANTI_DETECT_CONFIG_VERSION,
        ai_config=get_ai_config(db),
        device_config=DEVICE_CONFIG,
    )


@router.post("/progress")
async def report_progress(
    report: TaskProgressReport,
    _: None = Depends(verify_device_secret),
):
    """Device reports task execution progress. Broadcast to admin WS for real-time UI."""
    await pair_ws_manager.broadcast_to_admins({
        "event": "task_progress",
        "task_id": report.task_id,
        "step": report.step,
        "detail": report.detail,
        "progress": report.progress,
    })
    return {"ok": True}


@router.post("/report")
async def report_result(
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
        task, channel_broadcast_info = task_service.report_result(
            db=db,
            task_id=report.task_id,
            status=report.status,
            result=report.result,
            ui_snapshot=report.ui_snapshot,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")

    # Broadcast task status update to admin WS
    await pair_ws_manager.broadcast_to_admins({
        "event": "task_updated",
        "task_id": str(report.task_id),
        "status": str(report.status.value),
        "result": report.result or {},
    })

    # Broadcast channel progress via WS (BackgroundTasks runs after response)
    if channel_broadcast_info:
        from fastapi import BackgroundTasks
        bg = BackgroundTasks()
        bg.add_task(pair_ws_manager.broadcast_channel_progress,
                    channel_broadcast_info["channel_id"], channel_broadcast_info["stats"])
        if channel_broadcast_info.get("channel_completed"):
            bg.add_task(pair_ws_manager.broadcast_channel_completed,
                        channel_broadcast_info["channel_id"])
        from fastapi.encoders import jsonable_encoder
        return JSONResponse(content=jsonable_encoder(task), background=bg)

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
        await _notify_pending_tasks(db, device_id)
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


@router.get("/prompt-templates")
def get_prompt_templates(
    version: int = Query(0),
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    current_version, templates = prompt_template_service.get_all_templates(db)
    if version == current_version:
        return {"version": current_version, "templates": None, "changed": False}

    return {
        "version": current_version,
        "templates": templates,
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
        # Skip pending channel items for this account
        from app.services.channel_service import channel_service
        channel_service.on_risk_control(db, report.account_id)
        db.commit()
    return {"status": "acknowledged", "account_status": account.status}


class CommentRepliedRequest(BaseModel):
    author: str = Field(..., description="评论作者")
    text: str = Field(..., description="评论内容")


@router.post("/comment-claim-reply")
def claim_comment_reply(
    request: CommentRepliedRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """原子操作：检查+标记。返回 claimed=true 表示该设备可以回复，false 表示已被其他设备占用"""
    import hashlib
    content_hash = hashlib.sha256(
        (request.author + "|" + request.text).encode("utf-8")
    ).hexdigest()
    from app.db_models import RepliedComment
    existing = db.query(RepliedComment).filter(
        RepliedComment.content_hash == content_hash
    ).first()
    if existing:
        return {"claimed": False, "hash": content_hash}

    db.add(RepliedComment(
        content_hash=content_hash,
        author=request.author,
        text=request.text,
        replied_by_device=authed_device_id,
    ))
    db.commit()
    return {"claimed": True, "hash": content_hash}


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


@router.get("/templates")
def device_list_templates(
    _: Optional[str] = Depends(verify_device_secret),
):
    """Return template list with MD5 hashes for incremental sync."""
    from app.services.template_service import template_service
    templates = template_service.list_templates()
    return {"templates": templates}


@router.get("/templates/{filename}")
def device_download_template(
    filename: str,
    _: Optional[str] = Depends(verify_device_secret),
):
    """Download a single template image (binary)."""
    from app.services.template_service import template_service
    from fastapi.responses import FileResponse
    filepath = template_service.get_template_path(filename)
    if not filepath:
        raise HTTPException(status_code=404, detail="模板文件不存在")
    return FileResponse(str(filepath), media_type="image/png", filename=filename)


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
            json_body = {
                "model": ai_cfg.get("model", "deepseek-chat"),
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "messages": [{"role": "user", "content": request.prompt}],
            }
            if ai_cfg.get("thinking_enabled"):
                json_body["thinking"] = {"type": "enabled"}
            resp = await client.post(
                ai_cfg["api_url"],
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {ai_cfg.get('api_key', '')}",
                },
                json=json_body,
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

# --- 采集数据上报 ---

from app.models import CollectReportRequest, CollectCommentData, CollectUserData


@router.post("/collect-report")
def collect_report(
    request: CollectReportRequest,
    db: Session = Depends(get_db),
    device_id: str = Depends(verify_device_secret),
):
    from app.db_models import CollectedComment, CollectedUser
    from sqlalchemy.exc import IntegrityError

    # 1. 保存评论数据
    comment = CollectedComment(
        task_id=request.task_id,
        device_id=device_id,
        keyword=request.keyword,
        nickname=request.comment.nickname,
        content=request.comment.content,
        time_str=request.comment.time_str,
        reply_count=request.comment.reply_count,
        like_count=request.comment.like_count,
        dislike_count=request.comment.dislike_count,
        location=request.comment.location,
        is_author=request.comment.is_author,
    )
    db.add(comment)

    user_new = False
    if request.user and request.user.douyin_id:
        existing = db.query(CollectedUser).filter(
            CollectedUser.douyin_id == request.user.douyin_id
        ).first()
        if not existing:
            db.add(CollectedUser(
                task_id=request.task_id,
                device_id=device_id,
                nickname=request.user.nickname,
                douyin_id=request.user.douyin_id,
                likes_count=request.user.likes_count,
                follow_count=request.user.follow_count,
                fans_count=request.user.fans_count,
                works_count=request.user.works_count,
                gender=request.user.gender,
                age=request.user.age,
                ip_location=request.user.ip_location,
                is_private=request.user.is_private,
            ))
            user_new = True

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        user_new = False

    return {"comment_saved": True, "user_new": user_new}

