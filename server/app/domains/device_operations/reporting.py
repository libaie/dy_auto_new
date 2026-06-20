"""Device task reporting, heartbeat, and risk-report routes."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_device_secret
from app.models import RiskReport, StatsIncrementRequest, TaskProgressReport, TaskResultReport
from app.domains.task_operations.task_service import task_service
from app.ws_manager import pair_ws_manager
from app.domains.device_operations.status_ws import _notify_pending_tasks

logger = logging.getLogger(__name__)
router = APIRouter()
risk_router = APIRouter()


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
    from app.domains.reporting.stats_service import stats_service
    from app.db.models.reporting import StatsEvent
    from app.db_models import Task as DBTask

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
    from app.domains.device_operations.device_service import device_service
    status_changed = device_service.update_heartbeat(db, device_id, ip=client_ip)
    if status_changed:
        await pair_ws_manager.broadcast_to_admins({
            "event": "device_status_changed",
            "device_id": device_id,
            "status": "online",
        })
        await _notify_pending_tasks(db, device_id)
    return {"status": "ok", "device_id": device_id}

@risk_router.post("/risk-report")
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
        from app.domains.account_operations.channel_service import channel_service
        channel_service.on_risk_control(db, report.account_id)
        db.commit()
        await pair_ws_manager.broadcast_to_admins({"event": "accounts_changed"})
    return {"status": "acknowledged", "account_status": account.status}
