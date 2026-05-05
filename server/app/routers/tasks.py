"""Task management API -- create, list, get tasks."""
import logging
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session

from pydantic import BaseModel
from app.models import TaskCreateRequest, BatchTaskCreateRequest, TaskStatus, TASK_PARAMS_VALIDATORS
from app.database import get_db
from app.db_models import Device
from app.deps import verify_admin_token
from app.services.task_service import task_service

logger = logging.getLogger(__name__)

# Task types that use content (comments, DMs, replies)
CONTENT_TASK_TYPES = {"search_comment", "search_dm", "reply_comment"}

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


async def _maybe_resolve_template(db: Session, params: dict, task_type: str) -> dict:
    """If task has content_template_id and is a content-using type, generate content.

    On any failure, records error in params and returns unchanged (task created without content).
    """
    template_id = params.get("content_template_id")
    if not template_id:
        return params

    if task_type not in CONTENT_TASK_TYPES:
        return params

    try:
        from app.services.content_service import content_service
        tpl = content_service.get_template(db, template_id, check_active=True)
        if not tpl:
            raise ValueError(f"Template not found: {template_id}")
        # Whitelist: only pass context keys that match template variables
        if tpl.variables:
            context = {k: v for k, v in params.items()
                       if k in tpl.variables and isinstance(v, str)}
        else:
            context = {}
        content = await content_service.generate_from_template(db, template_id, context)
        params["content"] = content
    except Exception as e:
        logger.warning("Failed to resolve template %s at task creation: %s", template_id, e)
        params["_content_generation_error"] = str(e)

    return params


async def _maybe_expand_keywords(params: dict, task_type: str, db=None) -> dict:
    """If nurture task has keywords (seed), expand them into keyword_matrix via AI."""
    if task_type != "nurture":
        return params

    keywords = params.get("keywords")
    if not keywords or not isinstance(keywords, list) or len(keywords) == 0:
        return params

    # Skip if keyword_matrix already provided
    if params.get("keyword_matrix"):
        return params

    try:
        from app.services.content_service import content_service
        all_expanded = []
        for seed in keywords:
            seed = str(seed).strip()
            if not seed:
                continue
            expanded = await content_service.generate_keyword_matrix(seed, 8, db=db)
            all_expanded.extend(expanded)
        # Deduplicate while preserving order, seed keywords first
        seen = set(keywords)
        unique = list(keywords)
        for kw in all_expanded:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        params["keyword_matrix"] = unique
        logger.info("Expanded %d seed keywords into %d matrix keywords", len(keywords), len(unique))
    except Exception as e:
        logger.warning("Failed to expand keywords for nurture task: %s", e)
        params["keyword_matrix"] = [str(k).strip() for k in keywords if str(k).strip()]

    return params


@router.post("")
async def create_task(
    request: TaskCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    # 校验任务参数
    validator = TASK_PARAMS_VALIDATORS.get(request.type.value)
    if validator:
        try:
            if isinstance(validator, type) and issubclass(validator, BaseModel):
                # Pydantic model validator
                validated = validator(**request.params)
                params = validated.model_dump(exclude_none=True)
            else:
                # Function validator (e.g., nurture)
                params = validator(request.params)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"参数校验失败: {e}")
    else:
        params = dict(request.params)

    # Validate device_id if specified
    device_id = request.device_id
    if device_id:
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="设备不存在")
        if device.bound_account_id and device.bound_account_id != request.account_id:
            raise HTTPException(status_code=400, detail="该设备绑定的账号与任务账号不一致")

    params = await _maybe_expand_keywords(params, request.type.value, db=db)
    params = await _maybe_resolve_template(db, params, request.type.value)
    task = task_service.create_task(
        db=db,
        task_type=request.type,
        account_id=request.account_id,
        params=params,
        scheduled_at=request.scheduled_at,
        device_id=device_id,
    )

    # Notify device(s) that a new task is available — device must poll/claim via /poll
    # (sending full task via WS would bypass the claim state machine, quota checks, and scheduled_at)
    import logging
    logger = logging.getLogger(__name__)
    from app.ws_manager import pair_ws_manager
    if task.device_id:
        sent = await pair_ws_manager.send_to_device(task.device_id, {
            "event": "new_task_available",
        })
        logger.info(f"[task-create] 任务 {task.id} 指派设备 {task.device_id}，通知: {'成功' if sent else '设备离线'}")
    elif task.account_id:
        bound_device = db.query(Device).filter(Device.bound_account_id == task.account_id).first()
        if bound_device:
            sent = await pair_ws_manager.send_to_device(bound_device.id, {
                "event": "new_task_available",
            })
            logger.info(f"[task-create] 任务 {task.id} 账号 {task.account_id} 绑定设备 {bound_device.id}，通知: {'成功' if sent else '设备离线'}")
        else:
            await pair_ws_manager.broadcast_to_devices({
                "event": "new_task_available",
            })
            logger.info(f"[task-create] 任务 {task.id} 账号 {task.account_id} 无绑定设备，广播通知")
    else:
        await pair_ws_manager.broadcast_to_devices({
            "event": "new_task_available",
        })

    return task


@router.post("/batch")
async def batch_create_tasks(
    request: BatchTaskCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    # Resolve group_ids to account_ids
    account_ids = list(request.account_ids or [])
    if request.group_ids:
        from app.services.chain_service import chain_service
        group_accounts = chain_service.resolve_accounts_from_groups(db, request.group_ids)
        account_ids = list(set(account_ids + group_accounts))

    if not account_ids:
        raise HTTPException(status_code=422, detail="没有可用的账号")

    # Validate device_id if specified
    device_id = request.device_id
    if device_id:
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="设备不存在")
        # If device is bound to an account, that account must be in the batch
        if device.bound_account_id and device.bound_account_id not in account_ids:
            raise HTTPException(status_code=400, detail="该设备绑定的账号不在批量任务的账号列表中")

    # Validate params once
    validator = TASK_PARAMS_VALIDATORS.get(request.type.value)
    if validator:
        try:
            if isinstance(validator, type) and issubclass(validator, BaseModel):
                validated = validator(**request.params)
                params = validated.model_dump(exclude_none=True)
            else:
                params = validator(request.params)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"参数校验失败: {e}")
    else:
        params = dict(request.params)

    # AI expand keywords for all task types
    params = await _maybe_expand_keywords(params, request.type.value, db=db)

    # Extract keywords: use keyword_matrix (AI expanded) first, then keywords (seed), then keyword (single)
    keyword_list = (params.get("keyword_matrix")
                    or params.get("keywords")
                    or ([params.get("keyword")] if params.get("keyword") else []))

    # Auto-create channel when group_ids provided (handles multi-device concurrency)
    if request.group_ids and keyword_list:
        from app.services.channel_service import channel_service
        created_channels = []
        for group_id in request.group_ids:
            channel = channel_service.create_channel(
                db=db,
                group_id=group_id,
                task_type=request.type.value,
                account_mode="round_robin",
                keywords=keyword_list,
                params_template=params,
                account_id=request.account_ids[0] if request.account_ids else None,
            )
            created_channels.append({
                "channel_id": channel.id,
                "group_id": group_id,
                "total_items": channel.total_keywords,
            })

        # Notify devices
        from app.ws_manager import pair_ws_manager
        await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})

        return {"created": len(keyword_list) * len(request.group_ids), "mode": "channel", "channels": created_channels}

    # Fallback: create individual tasks per account (no group_ids or no keywords)
    from app.ws_manager import pair_ws_manager
    created_tasks = []
    for account_id in account_ids:
        account_params = await _maybe_resolve_template(db, dict(params), request.type.value)
        task = task_service.create_task(
            db=db,
            task_type=request.type,
            account_id=account_id,
            params=dict(account_params),
            scheduled_at=request.scheduled_at,
            device_id=device_id,
        )
        created_tasks.append(task)

    # Notify device(s)
    if device_id:
        await pair_ws_manager.send_to_device(device_id, {"event": "new_task_available"})
    else:
        notified_devices = set()
        for task in created_tasks:
            bound_device = db.query(Device).filter(Device.bound_account_id == task.account_id).first()
            if bound_device and bound_device.id not in notified_devices:
                notified_devices.add(bound_device.id)
                await pair_ws_manager.send_to_device(bound_device.id, {"event": "new_task_available"})
        unbound_accounts = [
            t.account_id for t in created_tasks
            if not db.query(Device).filter(Device.bound_account_id == t.account_id).first()
        ]
        if unbound_accounts:
            await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})

    return {"created": len(created_tasks), "tasks": created_tasks}


@router.get("")
def list_tasks(
    status: Optional[TaskStatus] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    tasks = task_service.list_tasks(db=db, status=status, skip=skip, limit=limit)
    total = task_service.count_tasks(db=db, status=status)
    return {"tasks": tasks, "total": total}


@router.get("/{task_id}")
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    task = task_service.get_task(db=db, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    try:
        task = task_service.cancel_task(db=db, task_id=task_id)
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail="Task not found")
        raise HTTPException(status_code=400, detail=str(e))

    # Push cancel to the device running this task (device_id is set when task is running)
    if task.device_id:
        from app.ws_manager import pair_ws_manager
        await pair_ws_manager.send_to_device(task.device_id, {
            "event": "cancel_task",
            "task_id": task.id,
        })

    return task
