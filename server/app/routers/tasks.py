"""Task management API -- create, list, get tasks."""
import logging
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session

from app.models import TaskCreateRequest, TaskStatus, TASK_PARAMS_VALIDATORS, KeywordMatrixRequest
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

    params = await _maybe_resolve_template(db, params, request.type.value)
    task = task_service.create_task(
        db=db,
        task_type=request.type,
        account_id=request.account_id,
        params=params,
        scheduled_at=request.scheduled_at,
        device_id=device_id,
    )

    # Push task to assigned device via WS
    if task.device_id:
        from app.ws_manager import pair_ws_manager
        await pair_ws_manager.send_to_device(task.device_id, {
            "event": "task",
            "task": task.model_dump(mode="json"),
        })

    return task


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
