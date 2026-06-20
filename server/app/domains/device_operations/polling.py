"""Device task polling routes."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import ANTI_DETECT_CONFIG, ANTI_DETECT_CONFIG_VERSION, DEVICE_CONFIG, bj_now
from app.database import get_db
from app.deps import verify_device_secret
from app.models import PollResponse
from app.services.prompt_template_service import prompt_template_service
from app.services.selector_service import selector_service
from app.services.task_service import task_service
from app.ws_manager import pair_ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()


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
    from app.domains.device_operations.device_service import device_service
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

    from app.domains.device_operations.device_service import device_service
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
