"""Device-facing API — poll, report, heartbeat, selectors."""
import logging
from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File as FastAPIFile, WebSocket, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
import asyncio
import io

logger = logging.getLogger(__name__)

from app.models import (
    TaskProgressReport, TaskResultReport, PollResponse, DeviceRegisterRequest,
    DeviceRegisterResponse, RiskReport, DeviceGenerateRequest, DeviceGenerateResponse,
    DeviceAIProxyRequest, DeviceAIProxyResponse, PairRequestCreate, PairStatusResponse,
    CollectReportRequest, CollectCommentData, CollectUserData,
    DMClaimRecipientRequest, DMClaimRecipientResponse,
    DMSendReportRequest, DMReleaseRecipientRequest, DMReleaseRecipientResponse,
    StatsIncrementRequest,
)
from app.database import get_db
from app.deps import verify_device_secret, verify_admin_token
from app.services.task_service import task_service
from app.config import ANTI_DETECT_CONFIG, ANTI_DETECT_CONFIG_VERSION, DEVICE_CONFIG, bj_now
from app.services.selector_service import selector_service
from app.services.prompt_template_service import prompt_template_service
from app.ws_manager import pair_ws_manager

router = APIRouter(prefix="/api/device", tags=["device"])

# In-memory rate limiter for unauthenticated endpoints (pair-request)
_pair_rate_limits: dict[str, list] = {}  # IP → [timestamps]


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

    now = bj_now()
    device_user_id = device.user_id

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

    pending_task_query = db.query(DBTask).filter(
        DBTask.status == TaskStatus.PENDING.value,
        route_filter,
        or_(DBTask.scheduled_at.is_(None), DBTask.scheduled_at <= now),
    )
    if device_user_id:
        pending_task_query = pending_task_query.filter(
            or_(DBTask.user_id == device_user_id, DBTask.user_id.is_(None))
        )
    pending_tasks = pending_task_query.all()

    # Also check pending channel items for this device
    from app.db_models import ChannelItem, Channel
    channel_subquery = db.query(Channel.id).filter(
        Channel.status == "active", Channel.deleted_at.is_(None)
    )
    if device_user_id:
        channel_subquery = channel_subquery.filter(
            or_(Channel.user_id == device_user_id, Channel.user_id.is_(None))
        )
    channel_item_query = db.query(ChannelItem).filter(
        ChannelItem.status == "pending",
        ChannelItem.channel_id.in_(channel_subquery),
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
async def ws_device_status(websocket: WebSocket):
    """Device maintains a persistent WS connection for status tracking.
    Server detects disconnect immediately → marks device offline → broadcasts to admins.

    Authentication: device sends {"type":"auth","device_id":"...","secret":"..."}
    as the first message after connect (not in URL).
    """
    from app.db_models import Device
    from app.config import DEVICE_SECRET

    await websocket.accept()

    # Read auth message (first message after connect)
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10)
    except (asyncio.TimeoutError, Exception):
        await websocket.close(code=4001, reason="Auth timeout or invalid message")
        return

    device_id = auth_msg.get("device_id", "")
    secret = auth_msg.get("secret", "")

    if not secret or not device_id:
        await websocket.close(code=4001, reason="Missing device_id or secret")
        return

    db = next(get_db())
    try:
        if secret != DEVICE_SECRET:
            device = db.query(Device).filter(Device.device_secret == secret).first()
            if not device:
                await websocket.close(code=4001, reason="Invalid secret")
                return
            device_id = device.id

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

        import logging
        _ws_log = logging.getLogger("device_ws")
        from starlette.websockets import WebSocketDisconnect
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(websocket.receive_text(), timeout=120)
                    if msg == '{"event":"device_disconnect"}':
                        _ws_log.info("device %s disconnected (explicit), marking offline", device_id)
                        try:
                            dev = db.query(Device).filter(Device.id == device_id).first()
                            if dev:
                                dev.status = "offline"
                                dev.last_seen_at = bj_now()
                                db.commit()
                        except Exception:
                            _ws_log.warning("device %s offline mark failed", device_id, exc_info=True)
                        await pair_ws_manager.broadcast_to_admins({
                            "event": "device_status_changed",
                            "device_id": device_id,
                            "status": "offline",
                        })
                        break
                    if msg == "ping":
                        await websocket.send_text("pong")
                        # Record heartbeat in memory — _offline_checker flushes to DB
                        pair_ws_manager.record_heartbeat(device_id, bj_now())
                except asyncio.TimeoutError:
                    try:
                        await websocket.send_text("ping")
                        msg = await asyncio.wait_for(websocket.receive_text(), timeout=10)
                    except asyncio.TimeoutError:
                        _ws_log.warning("device %s unresponsive to ping", device_id)
                        break
                    except WebSocketDisconnect:
                        _ws_log.info("device %s disconnected during ping probe", device_id)
                        break
                    except Exception:
                        _ws_log.warning("device %s error during ping probe", device_id, exc_info=True)
                        break
                except WebSocketDisconnect as dis:
                    _ws_log.info("device %s disconnected (code=%s)", device_id, dis.code)
                    break
        except Exception:
            _ws_log.warning("device %s WS loop exited with error", device_id, exc_info=True)
        finally:
            # 只在本连接仍是活跃连接时才清理（避免重连竞态）
            # WS 断开不标记离线 — _offline_checker 通过心跳超时统一判定
            if pair_ws_manager._device_status_connections.get(device_id) is websocket:
                pair_ws_manager.unregister_device_status(device_id)
    finally:
        db.close()


@router.get("/poll", response_model=PollResponse)
async def poll_tasks(
    device_id: str = Query(...),
    db: Session = Depends(get_db),
    authed_device_id: Optional[str] = Depends(verify_device_secret),
):
    # Per-device secret: use the verified device_id, reject mismatch
    if authed_device_id and authed_device_id != device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")
    if authed_device_id:
        device_id = authed_device_id

    # HTTP poll itself is a heartbeat — update last_seen_at
    from app.services.device_service import device_service
    device_service.update_heartbeat(db, device_id)

    # Check cancellation FIRST — if there's a pending cancel, deliver it
    # before dispatching any new task (prevents concurrent cancel+dispatch).
    cancelled_task = task_service.check_cancelled_running(db, device_id)
    if cancelled_task:
        logger.info("[poll] device=%s delivering cancelled_task_id=%s (skipping dispatch)",
            device_id, cancelled_task.id[:8])
        return PollResponse(
            task=None,
            selectors_version=selector_service.get_version(db),
            prompt_templates_version=prompt_template_service.get_version(db),
            proxy=None,
            cancelled_task_id=cancelled_task.id,
            anti_detect_config=ANTI_DETECT_CONFIG,
            anti_detect_config_version=ANTI_DETECT_CONFIG_VERSION,
            device_config=DEVICE_CONFIG,
            server_date=bj_now().strftime("%Y-%m-%d"),
        )

    # Resume running task on reconnect — device may have lost in-memory state.
    # If this device already has a RUNNING task, return it so the device can
    # resume execution instead of idling forever waiting for a new task.
    from app.db_models import Task as DBTask
    from app.models import TaskStatus
    from app.services.task_service import _db_task_to_pydantic
    running_task = db.query(DBTask).filter(
        DBTask.device_id == device_id,
        DBTask.status == TaskStatus.RUNNING.value,
    ).order_by(DBTask.started_at.desc()).first()
    if running_task:
        task = _db_task_to_pydantic(running_task)
        logger.info("[poll] device=%s resuming running task=%s type=%s",
            device_id, running_task.id[:8], running_task.type)
    else:
        task = task_service.get_pending_task(db, device_id)

    version = selector_service.get_version(db)
    tmpl_version = prompt_template_service.get_version(db)

    # 设备领到任务 → 通知前端任务列表更新
    if task:
        await pair_ws_manager.broadcast_to_admins({
            "event": "task_updated",
            "task_id": task.id,
            "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
        })

    from app.services.device_service import device_service
    device_info = device_service.get_device_status(db, device_id)
    proxy = device_info.get("proxy_config") if device_info else None

    # DM sequence templates for device sync — include sequences referenced by this task.
    from app.services.dm_sequence_visibility import get_device_visible_dm_sequences
    task_seq_id = (task.params or {}).get("dm_sequence_id") if task else None
    dm_seqs = get_device_visible_dm_sequences(
        db,
        device_id,
        extra_sequence_ids=[task_seq_id] if task_seq_id else None,
    )
    dm_sequences_list = [
        {
            "id": s.id,
            "messages": s.messages,
            "variants": s.variants,
        }
        for s in dm_seqs
    ] if dm_seqs else None
    logger.info("[poll] device=%s dm_sequences count=%s ids=%s",
        device_id,
        len(dm_sequences_list) if dm_sequences_list else 0,
        [s["id"][:8] for s in dm_sequences_list] if dm_sequences_list else [])
    if dm_sequences_list:
        for ds in dm_sequences_list:
            msgs = ds.get("messages", [])
            logger.info("[poll] dm_seq id=%s msg_count=%s msg_preview=%s",
                ds["id"][:8], len(msgs),
                [m.get("content","")[:30] for m in msgs[:2]] if msgs else [])

    from app.config import get_ai_config

    if task:
        logger.info("[poll] device=%s dispatching task_id=%s type=%s dm_seq_id=%s dm_messages=%s",
            device_id, task.id[:8], task.type,
            (task.params or {}).get("dm_sequence_id", "NONE"),
            "PRESENT" if (task.params or {}).get("dm_messages") else "NONE")

    return PollResponse(
        task=task,
        selectors_version=version,
        prompt_templates_version=tmpl_version,
        proxy=proxy,
        cancelled_task_id=None,
        anti_detect_config=ANTI_DETECT_CONFIG,
        anti_detect_config_version=ANTI_DETECT_CONFIG_VERSION,
        ai_config=get_ai_config(db),
        device_config=DEVICE_CONFIG,
        dm_sequences=dm_sequences_list,
        server_date=bj_now().strftime("%Y-%m-%d"),
    )


@router.post("/progress")
async def report_progress(
    report: TaskProgressReport,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """Device reports task execution progress. Broadcast to admin WS for real-time UI."""
    from app.db_models import Task as DBTask
    db_task = db.query(DBTask).filter(DBTask.id == report.task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    if report.lease_id and db_task.lease_id:
        if db_task.lease_id != report.lease_id:
            return {"ok": True, "stale": True, "message": "Progress ignored (stale lease)"}
    elif db_task.device_id != authed_device_id:
        raise HTTPException(status_code=403, detail="Task does not belong to this device")

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
    # Verify lease: accept current lease, log stale reports, fall back to device_id
    if authed_device_id:
        from app.db_models import Task as DBTask
        db_task = db.query(DBTask).filter(DBTask.id == report.task_id).first()
        if not db_task:
            raise HTTPException(status_code=404, detail="Task not found")
        if report.lease_id and db_task.lease_id:
            if db_task.lease_id != report.lease_id:
                logger.warning("device=%s task=%s stale result report (lease mismatch: reported=%s current=%s) — result logged for audit, not applied",
                    authed_device_id, report.task_id, report.lease_id[:8], db_task.lease_id[:8] if db_task.lease_id else "None")
                return {"ok": True, "stale": True, "message": "Result recorded for audit (stale lease)"}
        elif db_task.device_id != authed_device_id:
            raise HTTPException(status_code=403, detail="Task does not belong to this device")

    try:
        task, channel_broadcast_info = task_service.report_result(
            db=db,
            task_id=report.task_id,
            status=report.status,
            result=report.result,
            ui_snapshot=report.ui_snapshot,
        )
        db.commit()
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")

    # Broadcast task status update to admin WS
    await pair_ws_manager.broadcast_to_admins({
        "event": "task_updated",
        "task_id": str(report.task_id),
        "status": str(report.status.value),
        "result": report.result or {},
    })

    # 通知所有在线设备有新任务可领取（通道内可能有下一批待执行 item）
    if report.status.value in ("completed", "failed"):
        await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})

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


@router.post("/stats/increment")
def stats_increment(
    body: StatsIncrementRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """设备端增量统计上报——idempotent: 同一 (task,device,type,target,op_index) 只计一次。
    校验 task→account 归属和 task→device 归属，防止跨账号伪造统计。
    """
    from app.services.stats_service import stats_service
    from app.db_models import Task as DBTask, StatsEvent

    # 1. Validate task exists and belongs to the claimed account
    db_task = db.query(DBTask).filter(DBTask.id == body.task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    if db_task.account_id != body.account_id:
        raise HTTPException(status_code=403, detail="Task does not belong to this account")
    if db_task.device_id != authed_device_id:
        raise HTTPException(status_code=403, detail="Task not assigned to this device")

    # 2. Idempotent insert — duplicate key → skip count increment
    from sqlalchemy.exc import IntegrityError
    import logging
    _stats_log = logging.getLogger("device.stats_increment")
    try:
        evt = StatsEvent(
            task_id=body.task_id,
            device_id=authed_device_id,
            account_id=body.account_id,
            event_type=body.task_type,
            target_id=body.target_id,
            op_index=body.op_index,
            count=body.count,
        )
        db.add(evt)
        db.flush()
    except IntegrityError:
        db.rollback()
        # Duplicate event — already counted, return success
        return {"ok": True, "duplicate": True}
    except Exception:
        db.rollback()
        _stats_log.exception("stats insert failed: task=%s type=%s target=%s",
                             body.task_id, body.task_type, body.target_id)
        raise HTTPException(status_code=500, detail="Stats insert failed")

    # 3. Increment daily stats counter (only on first insert)
    stats_service.increment(db, body.account_id, body.task_type, count=body.count)
    db.commit()
    return {"ok": True}


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
    device_id: str = Depends(verify_device_secret),
):

    current_version, selectors = selector_service.get_all_selectors(db, device_id=device_id)
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
    user = Depends(verify_admin_token),
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
async def report_risk(
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
        await pair_ws_manager.broadcast_to_admins({"event": "accounts_changed"})
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
    from sqlalchemy.exc import IntegrityError
    content_hash = hashlib.sha256(
        (request.author + "|" + request.text).encode("utf-8")
    ).hexdigest()
    from app.db_models import RepliedComment
    # INSERT first — PK collision triggers IntegrityError, no SELECT+INSERT race window
    db.add(RepliedComment(
        content_hash=content_hash,
        author=request.author,
        text=request.text,
        replied_by_device=authed_device_id,
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"claimed": False, "hash": content_hash}
    return {"claimed": True, "hash": content_hash}


@router.post("/comment-claim-release")
def release_comment_claim(
    request: CommentRepliedRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """回复失败时释放占位，避免误标记为已回复"""
    import hashlib
    content_hash = hashlib.sha256(
        (request.author + "|" + request.text).encode("utf-8")
    ).hexdigest()
    from app.db_models import RepliedComment
    db.query(RepliedComment).filter(
        RepliedComment.content_hash == content_hash,
        RepliedComment.replied_by_device == authed_device_id,
    ).delete()
    db.commit()
    return {"released": True}


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
    device_id: str = Depends(verify_device_secret),
    db: Session = Depends(get_db),
    resolution: str = Query(None),
):
    """Return template list with MD5 hashes for incremental sync.
    Filters by device resolution profile when available."""
    from app.services.template_service import template_service
    if not resolution and device_id:
        device = db.query(Device).filter(Device.id == device_id).first()
        if device and device.screen_resolution:
            resolution = device.screen_resolution
    templates = template_service.list_templates(resolution=resolution)
    return {"templates": templates}


@router.get("/templates/{filename}")
def device_download_template(
    filename: str,
    device_id: str = Depends(verify_device_secret),
    db: Session = Depends(get_db),
    resolution: str = Query(None),
):
    """Download a single template image (binary).
    Priority: explicit resolution query param > device resolution > default."""
    from app.db_models import Device
    from app.services.template_service import template_service
    from fastapi.responses import FileResponse
    if not resolution:
        resolution = "default"
        if device_id:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device and device.screen_resolution:
                resolution = device.screen_resolution
    filepath = template_service.get_template_path(filename, resolution=resolution)
    if not filepath:
        raise HTTPException(status_code=404, detail="模板文件不存在")
    return FileResponse(str(filepath), media_type="image/png", filename=filename)


class CalibrationItem(BaseModel):
    action_name: str
    filename: str
    data: str  # base64-encoded PNG


class CalibrationRequest(BaseModel):
    templates: list[CalibrationItem]
    resolution: str = ""


@router.post("/calibrate")
async def device_calibrate(
    request: CalibrationRequest,
    db: Session = Depends(get_db),
    device_id: str = Depends(verify_device_secret),
):
    """Device uploads auto-calibrated image templates.
    Saves templates and upserts UISelector rows for this resolution profile."""
    import base64
    from app.services.template_service import template_service
    from app.db_models import UISelector, Device

    resolution = request.resolution
    if not resolution:
        device = db.query(Device).filter(Device.id == device_id).first()
        if device and device.screen_resolution:
            resolution = device.screen_resolution
    if not resolution:
        raise HTTPException(status_code=400, detail="无法确定设备分辨率")

    uploaded = 0
    for item in request.templates:
        # Decode and save template
        try:
            content = base64.b64decode(item.data)
        except Exception:
            continue
        template_service.save_template(item.filename, content, resolution=resolution)

        # Upsert selector: clone existing "default" profile selector for this resolution
        existing = db.query(UISelector).filter(
            UISelector.action_name == item.action_name,
            UISelector.resolution_profile == resolution,
        ).first()
        if not existing:
            # Clone from default profile if it exists
            default_sel = db.query(UISelector).filter(
                UISelector.action_name == item.action_name,
                UISelector.resolution_profile == "default",
            ).first()
            if default_sel:
                # Clone strategies but update image template references to the
                # newly uploaded file (original references default templates).
                import copy
                new_strategies = copy.deepcopy(default_sel.strategies)
                for st in new_strategies:
                    if st.get("type") == "image":
                        st["template"] = item.filename
                new_sel = UISelector(
                    action_name=item.action_name,
                    description=default_sel.description,
                    platform_version=default_sel.platform_version,
                    resolution_profile=resolution,
                    strategies=new_strategies,
                    version=1,
                    category=default_sel.category,
                    purpose=default_sel.purpose,
                    strategy_logic=default_sel.strategy_logic,
                    extract_field=default_sel.extract_field,
                    clean_mode=default_sel.clean_mode,
                    clean_pattern=default_sel.clean_pattern,
                    clean_prompt=default_sel.clean_prompt,
                )
                db.add(new_sel)
        uploaded += 1

    from app.services.selector_service import _bump_revision
    _bump_revision(db)
    db.commit()

    # Broadcast version bump
    version = selector_service.get_version(db)
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({"event": "selectors_changed"})

    return {"uploaded": uploaded, "resolution": resolution}


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
            model = ai_cfg.get("model", "deepseek-chat")
            json_body = {
                "model": model,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "messages": [{"role": "user", "content": request.prompt}],
            }
            # thinking 参数仅在 deepseek-reasoner 或明确支持 thinking 的模型上发送
            if ai_cfg.get("thinking_enabled") and ("reasoner" in model.lower() or "r1" in model.lower()):
                json_body["thinking"] = {"type": "enabled"}
            logger.debug("AI proxy request: model=%s max_tokens=%s temp=%s prompt_len=%s thinking=%s",
                          model, request.max_tokens, request.temperature, len(request.prompt),
                          "thinking" in json_body)
            resp = await client.post(
                ai_cfg["api_url"],
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {ai_cfg.get('api_key', '')}",
                },
                json=json_body,
            )
        if resp.status_code != 200:
            logger.error("AI API error: status=%s body=%s", resp.status_code, resp.text[:500])
            raise HTTPException(status_code=502, detail=f"AI API error: {resp.status_code}")
        result = resp.json()
        logger.debug("AI API response: %s", {k: str(v)[:200] for k, v in result.items() if k != "choices"})
        content = (result.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        if not content:
            logger.error("AI API returned empty content. Full response: %s", str(result)[:1000])
        return DeviceAIProxyResponse(content=content)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI API timeout")
    except (KeyError, IndexError) as e:
        logger.error("Invalid AI response structure: %s", e)
        raise HTTPException(status_code=502, detail=f"Invalid AI response: {e}")

# --- 采集数据上报 ---


_dest_cache: dict[str, dict] = {}

async def _resolve_destination(keyword: str, db) -> dict | None:
    """服务端解析旅游关键词→省份/城市/景点，按 keyword 缓存。"""
    if not keyword or keyword in _dest_cache:
        return _dest_cache.get(keyword)
    from app.services.ai_generator import ai_generator
    try:
        raw = await ai_generator.generate_custom(
            db,
            "只输出 JSON，不要其他文本。",
            "将以下旅游关键词解析为目的地信息。\n关键词：" + keyword + "\n输出格式：{\"province\":\"省份\",\"city\":\"城市\",\"attraction\":\"景点\"}\n如果关键词本身是省份或城市，对应字段填空字符串。",
            max_tokens=200, temperature=0.1,
        )
        import json
        m = __import__("re").search(r'\{[\s\S]*\}', raw)
        if m:
            data = json.loads(m.group(0))
            _dest_cache[keyword] = data
            return data
    except Exception:
        pass
    _dest_cache[keyword] = None
    return None


@router.post("/collect-report")
async def collect_report(
    request: CollectReportRequest,
    db: Session = Depends(get_db),
    device_id: str = Depends(verify_device_secret),
):
    from app.db_models import CollectedComment, CollectedUser
    from sqlalchemy.exc import IntegrityError

    # 1. 解析目的地（设备端未传时服务端兜底，仅旅游行业任务触发）
    _is_travel = False
    has_dest = (request.comment.intended_province or request.comment.intended_city or request.comment.intended_attraction)
    if not has_dest and request.keyword and request.task_id:
        from app.db_models import Task
        task = db.query(Task).filter(Task.id == request.task_id).first()
        if task and task.params:
            tid = task.params.get("prompt_template_id")
            if tid:
                from app.db_models import PromptTemplate
                pt = db.query(PromptTemplate).filter(PromptTemplate.id == tid).first()
                _is_travel = pt and pt.industry == "travel"
    if _is_travel and not has_dest and request.keyword:
        dest = await _resolve_destination(request.keyword, db)
        if dest:
            if not request.comment.intended_province:
                request.comment.intended_province = dest.get("province")
            if not request.comment.intended_city:
                request.comment.intended_city = dest.get("city")
            if not request.comment.intended_attraction:
                request.comment.intended_attraction = dest.get("attraction")

    # 2. 保存评论（独立提交，用户去重失败不影响评论落库）
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
        data_source_type=request.data_source_type,
        ai_reply=request.comment.ai_reply,
        ai_replied_at=bj_now() if request.comment.ai_reply else None,
        intended_province=request.comment.intended_province or None,
        intended_city=request.comment.intended_city or None,
        intended_attraction=request.comment.intended_attraction or None,
    )
    db.add(comment)
    db.commit()  # 评论独立提交

    # 2. 保存用户（存在则更新，不存在则新建）
    user_new = False
    if request.user and request.user.douyin_id:
        existing = db.query(CollectedUser).filter(
            CollectedUser.douyin_id == request.user.douyin_id
        ).first()
        if existing:
            existing.nickname = request.user.nickname
            existing.likes_count = request.user.likes_count
            existing.follow_count = request.user.follow_count
            existing.fans_count = request.user.fans_count
            existing.works_count = request.user.works_count
            existing.gender = request.user.gender
            existing.age = request.user.age
            existing.ip_location = request.user.ip_location
            existing.is_private = request.user.is_private
            existing.data_source_type = request.data_source_type
            existing.keyword = request.keyword
            existing.task_id = request.task_id
            existing.device_id = device_id
            if request.comment.intended_province:
                existing.intended_province = request.comment.intended_province
            if request.comment.intended_city:
                existing.intended_city = request.comment.intended_city
            if request.comment.intended_attraction:
                existing.intended_attraction = request.comment.intended_attraction
            db.commit()
        else:
            db.add(CollectedUser(
                task_id=request.task_id,
                device_id=device_id,
                keyword=request.keyword,
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
                data_source_type=request.data_source_type,
                intended_province=request.comment.intended_province or None,
                intended_city=request.comment.intended_city or None,
                intended_attraction=request.comment.intended_attraction or None,
            ))
            try:
                db.commit()
                user_new = True
            except IntegrityError:
                db.rollback()
                existing2 = db.query(CollectedUser).filter(
                    CollectedUser.douyin_id == request.user.douyin_id
                ).first()
                if existing2:
                    existing2.nickname = request.user.nickname
                    existing2.likes_count = request.user.likes_count
                    existing2.follow_count = request.user.follow_count
                    existing2.fans_count = request.user.fans_count
                    existing2.works_count = request.user.works_count
                    existing2.gender = request.user.gender
                    existing2.age = request.user.age
                    existing2.ip_location = request.user.ip_location
                    existing2.is_private = request.user.is_private
                    existing2.data_source_type = request.data_source_type
                    existing2.keyword = request.keyword
                    existing2.task_id = request.task_id
                    existing2.device_id = device_id
                    db.commit()

    # WS 实时推送
    await pair_ws_manager.broadcast_to_admins({"event": "data_changed", "type": "comment", "id": comment.id})
    if user_new:
        await pair_ws_manager.broadcast_to_admins({"event": "data_changed", "type": "user", "id": request.user.douyin_id})

    return {"comment_saved": True, "user_new": user_new}


# --- DM conversation endpoints ---

@router.post("/dm-claim-recipient", response_model=DMClaimRecipientResponse)
def dm_claim_recipient(
    request: DMClaimRecipientRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """原子占用：insert conversation where not exists (account_id, douyin_id).
    SQLite WAL 竞态：并发 SELECT 可能同时通过 → IntegrityError → claimed=false."""
    from app.db_models import Conversation
    from sqlalchemy.exc import IntegrityError
    from datetime import datetime, timezone, timedelta

    now = bj_now()

    # 清理孤儿 claim（超 30min 未发送）
    orphan_threshold = now - timedelta(minutes=30)
    db.query(Conversation).filter(
        Conversation.claimed_at.isnot(None),
        Conversation.claimed_at < orphan_threshold,
        Conversation.status == "active",
        Conversation.last_dm_at.is_(None),
    ).delete()
    db.flush()

    # 检查已有会话
    existing = db.query(Conversation).filter(
        Conversation.account_id == request.account_id,
        Conversation.recipient_douyin_id == request.recipient_douyin_id,
    ).first()
    if existing:
        return DMClaimRecipientResponse(claimed=False, conversation_id=None)

    conv = Conversation(
        task_id=None,
        account_id=request.account_id,
        device_id=authed_device_id,
        recipient_nickname=request.recipient_nickname,
        recipient_douyin_id=request.recipient_douyin_id,
        claimed_at=now,
    )
    db.add(conv)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return DMClaimRecipientResponse(claimed=False, conversation_id=None)

    db.refresh(conv)
    return DMClaimRecipientResponse(claimed=True, conversation_id=conv.id)


@router.post("/dm-send-report")
async def dm_send_report(
    request: DMSendReportRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """DM 发送成功后上报：更新 stage、content、计数"""
    from app.db_models import Conversation

    now = bj_now()
    conv = db.query(Conversation).filter(Conversation.id == request.conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    if conv.device_id != authed_device_id:
        raise HTTPException(status_code=403, detail="会话不属于此设备")

    conv.current_stage = request.stage
    conv.intent = request.intent
    conv.last_dm_content = request.content
    conv.last_dm_at = now
    conv.total_dm_count = (conv.total_dm_count or 0) + 1
    conv.claimed_at = None  # 清除 claim 标记
    if request.keyword and not conv.keyword:
        conv.keyword = request.keyword
    db.commit()

    await pair_ws_manager.broadcast_to_admins({
        "event": "data_changed", "type": "conversation", "id": conv.id,
    })
    return {"ok": True}


@router.post("/dm-release-recipient", response_model=DMReleaseRecipientResponse)
def dm_release_recipient(
    request: DMReleaseRecipientRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """DM 发送失败时释放占用。仅允许 claim 设备释放，防止误删其他设备的成功会话。"""
    from app.db_models import Conversation

    conv = db.query(Conversation).filter(
        Conversation.id == request.conversation_id,
        Conversation.device_id == authed_device_id,
        Conversation.last_dm_at.is_(None),  # 尚未成功发送过
    ).first()
    if conv:
        db.delete(conv)
        db.commit()
        return DMReleaseRecipientResponse(released=True)
    return DMReleaseRecipientResponse(released=False)


class CommentAIReplyRequest(BaseModel):
    nickname: str
    text: str
    ai_reply: str
    task_id: str | None = None
    intended_province: str | None = None
    intended_city: str | None = None
    intended_attraction: str | None = None


@router.post("/comment-ai-reply")
def save_comment_ai_reply(
    request: CommentAIReplyRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_device_secret),
):
    """保存 AI 生成的回复到采集的评论记录（按昵称+内容+task_id 匹配，避免跨视频错配）"""
    from app.db_models import CollectedComment
    query = db.query(CollectedComment).filter(
        CollectedComment.nickname == request.nickname,
        CollectedComment.content == request.text,
        CollectedComment.ai_reply.is_(None),
    )
    if request.task_id:
        query = query.filter(CollectedComment.task_id == request.task_id)
    comment = query.order_by(CollectedComment.created_at.desc()).first()
    if comment:
        comment.ai_reply = request.ai_reply
        comment.ai_replied_at = bj_now()
        if request.intended_province is not None:
            comment.intended_province = request.intended_province
        if request.intended_city is not None:
            comment.intended_city = request.intended_city
        if request.intended_attraction is not None:
            comment.intended_attraction = request.intended_attraction
        db.commit()
        return {"updated": True}
    return {"updated": False}


class UserProfileRequest(BaseModel):
    nickname: str
    douyin_id: str = ""
    fans_count: str = ""
    likes_count: str = ""
    follow_count: str = ""
    works_count: str = ""
    gender: str = ""
    age: str = ""
    ip_location: str = ""
    is_private: str = ""
    keyword: str = ""
    task_id: str = ""
    intended_province: str | None = None
    intended_city: str | None = None
    intended_attraction: str | None = None


@router.post("/user-profile")
def save_user_profile(
    request: UserProfileRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """保存采集到的用户主页数据，按 douyin_id 去重插入。"""
    from app.db_models import CollectedUser
    from sqlalchemy.exc import IntegrityError

    douyin_id = request.douyin_id.strip()
    if not douyin_id:
        return {"saved": False, "reason": "empty douyin_id"}

    existing = db.query(CollectedUser).filter(CollectedUser.douyin_id == douyin_id).first()
    if existing:
        # Update fields if they changed
        changed = False
        for field in ("nickname", "fans_count", "likes_count", "follow_count",
                       "works_count", "gender", "age", "ip_location", "is_private",
                       "keyword"):
            val = getattr(request, field, "") or ""
            if getattr(existing, field, None) != val:
                setattr(existing, field, val)
                changed = True
        for field in ("intended_province", "intended_city", "intended_attraction"):
            val = getattr(request, field, None)
            if val and getattr(existing, field, None) != val:
                setattr(existing, field, val)
                changed = True
        if changed:
            db.commit()
        return {"saved": True, "updated": changed, "user_id": existing.id}

    try:
        user = CollectedUser(
            nickname=request.nickname,
            douyin_id=douyin_id,
            keyword=request.keyword or "",
            task_id=request.task_id or None,
            fans_count=request.fans_count or "",
            likes_count=request.likes_count or "",
            follow_count=request.follow_count or "",
            works_count=request.works_count or "",
            gender=request.gender or "",
            age=request.age or "",
            ip_location=request.ip_location or "",
            is_private=request.is_private or "",
            device_id=authed_device_id,
            intended_province=request.intended_province or None,
            intended_city=request.intended_city or None,
            intended_attraction=request.intended_attraction or None,
        )
        db.add(user)
        db.commit()
        return {"saved": True, "updated": False, "user_id": user.id}
    except IntegrityError:
        db.rollback()
        return {"saved": False, "reason": "duplicate douyin_id"}


class UserAvatarRequest(BaseModel):
    douyin_id: str
    image_base64: str  # base64-encoded JPEG/PNG


@router.post("/user-avatar")
def upload_user_avatar(
    request: UserAvatarRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_device_secret),
):
    """上传用户头像裁剪图，保存到本地并关联 CollectedUser."""
    import base64
    import os
    from app.db_models import CollectedUser

    douyin_id = request.douyin_id.strip()
    if not douyin_id:
        return {"saved": False, "reason": "empty douyin_id"}

    user = db.query(CollectedUser).filter(CollectedUser.douyin_id == douyin_id).first()
    if not user:
        return {"saved": False, "reason": "user not found"}

    try:
        img_data = base64.b64decode(request.image_base64)
    except Exception:
        return {"saved": False, "reason": "invalid base64"}

    if len(img_data) > 512 * 1024:
        return {"saved": False, "reason": "image too large (>512KB)"}

    avatar_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    filename = f"{douyin_id}.jpg"
    filepath = os.path.join(avatar_dir, filename)
    with open(filepath, "wb") as f:
        f.write(img_data)

    user.avatar_url = f"/api/device/avatar/{douyin_id}"
    db.commit()
    return {"saved": True, "filename": filename, "size": len(img_data)}


@router.get("/avatar/{douyin_id}")
def get_user_avatar(douyin_id: str):
    """获取用户头像图片."""
    import os
    from fastapi.responses import FileResponse
    avatar_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "avatars")
    filepath = os.path.join(avatar_dir, f"{douyin_id}.jpg")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Avatar not found")
    return FileResponse(filepath, media_type="image/jpeg")

