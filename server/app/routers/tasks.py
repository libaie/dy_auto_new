"""Task management CRUD API — admin only."""
import logging

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token
from app.models import TaskType, TaskStatus
from app.services.task_service import task_service
from app.services.content_service import content_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskCreateRequest(BaseModel):
    type: TaskType
    account_id: Optional[str] = None
    device_id: Optional[str] = None
    params: dict = {}


class TaskBatchCreateRequest(BaseModel):
    type: TaskType
    group_ids: list[str] = []
    device_id: Optional[str] = None
    params: dict = {}


async def _maybe_expand_keywords(params: dict, task_type: str, db=None) -> dict:
    """If nurture task has keywords (seed), expand them into keyword_matrix via AI."""
    if task_type != "nurture" or "keywords" not in params:
        return params
    seeds = [k.strip() for k in params.get("keywords", []) if k and k.strip()]
    if not seeds:
        return params
    try:
        all_expanded = []
        for seed in seeds[:3]:
            expanded = await content_service.generate_keyword_matrix(seed, 8, db=db)
            all_expanded.extend(expanded)
        unique = list(dict.fromkeys(seeds + all_expanded))
        params["keyword_matrix"] = unique
        for kw in all_expanded:
            logger.info("AI expanded keyword: %s", kw)
    except Exception as e:
        logger.warning("Failed to expand keywords for nurture task: %s", e)
    return params


def _resolve_task_type(type_val) -> TaskType:
    if isinstance(type_val, TaskType):
        return type_val
    return TaskType(type_val)


@router.post("")
async def create_task(
    request: TaskCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    if not request.account_id:
        raise HTTPException(status_code=400, detail="account_id is required for single create")
    params = await _maybe_expand_keywords(request.params, request.type.value, db=db)
    try:
        task = task_service.create_task(
            db=db,
            task_type=request.type,
            account_id=request.account_id,
            params=params,
            device_id=request.device_id or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})
    return task


@router.post("/batch")
async def batch_create_tasks(
    request: TaskBatchCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    if not request.group_ids:
        raise HTTPException(status_code=400, detail="group_ids required for batch create")
    ttype = request.type.value

    from app.db_models import Account, Channel
    from app.models import TaskType as TT
    import uuid

    params = await _maybe_expand_keywords(request.params, ttype, db=db)
    keywords = params.get("keywords", []) or ([params.get("keyword")] if params.get("keyword") else [])

    created_tasks = []
    for gid in request.group_ids:
        channel = db.query(Channel).filter(Channel.id == gid).first()
        if not channel:
            channel = Channel(id=gid, name=f"group-{gid[:8]}", group_id=gid, status="active")
            db.add(channel)
            db.flush()

        accounts = db.query(Account).filter(Account.group == gid, Account.status == "active").all()
        if keywords:
            # Store common params (prompt_template_id, sort_by, etc.) as template
            # so claim_channel_item can merge them with each item's keyword
            channel.params_template = {k: v for k, v in params.items() if k not in ("keyword", "keywords", "keyword_matrix")}
            db.flush()
            from app.db_models import ChannelItem
            for kw in keywords:
                if not kw or not kw.strip():
                    continue
                for acc in accounts:
                    ci = ChannelItem(
                        channel_id=channel.id,
                        keyword=kw.strip(),
                        account_id=acc.id,
                        status="pending",
                        queue_position=len(created_tasks),
                    )
                    db.add(ci)
                    created_tasks.append({"keyword": kw.strip(), "account_id": acc.id})
        else:
            for acc in accounts:
                task = task_service.create_task(
                    db=db,
                    task_type=TT(ttype),
                    account_id=acc.id,
                    params=params,
                    device_id=request.device_id or None,
                )
                created_tasks.append({"id": task.id, "account_id": acc.id})

    db.commit()

    from app.db_models import Device
    from app.ws_manager import pair_ws_manager
    if any(t.get("id") for t in created_tasks):
        unbound_accounts = [
            t["account_id"] for t in created_tasks if t.get("id")
            if not db.query(Device).filter(Device.bound_account_id == t["account_id"]).first()
        ]
        if unbound_accounts:
            await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})
    else:
        await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})

    return {"created": len(created_tasks), "mode": "channel" if keywords else "direct"}


@router.get("")
def list_tasks(
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    tasks = task_service.list_tasks(db=db, status=status, task_type=type, search=search,
                                     sort_by=sort_by, sort_order=sort_order, skip=skip, limit=limit)
    total = task_service.count_tasks(db=db, status=status, task_type=type, search=search)
    return {"tasks": tasks, "total": total}


class BatchDeleteRequest(BaseModel):
    task_ids: list[str]


@router.post("/batch-delete")
def batch_delete_tasks(
    body: BatchDeleteRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    count = task_service.delete_tasks_batch(db, body.task_ids)
    return {"deleted": count}


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

    if task.device_id:
        from app.ws_manager import pair_ws_manager
        await pair_ws_manager.send_to_device(task.device_id, {
            "event": "cancel_task",
            "task_id": task.id,
        })

    return task


@router.delete("/{task_id}")
def delete_task(task_id: str, db=Depends(get_db), _=Depends(verify_admin_token)):
    try:
        task_service.delete_task(db=db, task_id=task_id)
    except ValueError as e:
        if "not found" in str(e): raise HTTPException(status_code=404, detail="Task not found")
        raise HTTPException(status_code=400, detail=str(e))
    return {"deleted": True, "task_id": task_id}
