"""Chain templates and instances API."""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.config import bj_now

from app.database import get_db
from app.db_models import ChainTemplate, ChainInstance, Task as DBTask, Account, Device, AccountGroupMember
from app.deps import verify_admin_token, require_role
from app.models import ChainTemplateCreate, ChainTemplateUpdate, ChainInstanceCreateRequest
from app.ws_manager import pair_ws_manager

router = APIRouter(prefix="/api/chains", tags=["chains"])


def _template_to_dict(t: ChainTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description or "",
        "steps": t.steps or [],
        "created_at": str(t.created_at) if t.created_at else None,
        "updated_at": str(t.updated_at) if t.updated_at else None,
    }


def _instance_to_dict(inst: ChainInstance, template_name: str = "", account_nickname: str = "", device_name: str = "") -> dict:
    return {
        "id": inst.id,
        "template_id": inst.template_id,
        "template_name": template_name,
        "account_id": inst.account_id,
        "account_nickname": account_nickname,
        "device_id": inst.device_id or "",
        "device_name": device_name,
        "current_step": inst.current_step,
        "total_steps": inst.total_steps,
        "status": inst.status,
        "created_at": str(inst.created_at) if inst.created_at else None,
        "started_at": str(inst.started_at) if inst.started_at else None,
        "completed_at": str(inst.completed_at) if inst.completed_at else None,
    }


# --- Chain Template CRUD ---

@router.post("/templates")
async def create_template(
    request: ChainTemplateCreate,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    user_id, _ = user
    orders = sorted(s.step_order for s in request.steps)
    if orders != list(range(1, len(request.steps) + 1)):
        raise HTTPException(status_code=422, detail="步骤序号必须从 1 连续递增")

    steps_data = [s.model_dump() for s in request.steps]
    tpl = ChainTemplate(name=request.name, description=request.description, steps=steps_data, user_id=user_id)
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    await pair_ws_manager.broadcast_to_admins({"event": "chains_changed"})
    return _template_to_dict(tpl)


@router.get("/templates")
def list_templates(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    user_id, role = user
    query = db.query(ChainTemplate)
    if role != "admin":
        query = query.filter(ChainTemplate.user_id == user_id)
    total = query.count()
    templates = query.order_by(ChainTemplate.created_at.desc()).offset(skip).limit(limit).all()
    return {"templates": [_template_to_dict(t) for t in templates], "total": total}


@router.get("/templates/{template_id}")
def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(ChainTemplate).filter(ChainTemplate.id == template_id)
    if role != "admin":
        query = query.filter(ChainTemplate.user_id == user_id)
    tpl = query.first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    return _template_to_dict(tpl)


@router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    request: ChainTemplateUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(ChainTemplate).filter(ChainTemplate.id == template_id)
    if role != "admin":
        query = query.filter(ChainTemplate.user_id == user_id)
    tpl = query.first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    if request.name is not None:
        tpl.name = request.name
    if request.description is not None:
        tpl.description = request.description
    if request.steps is not None:
        # Prevent modifying steps when active instances exist (template hot-update risk)
        active = db.query(ChainInstance).filter(
            ChainInstance.template_id == template_id,
            ChainInstance.status.in_(["pending", "running"]),
        ).count()
        if active > 0:
            raise HTTPException(
                status_code=400,
                detail=f"该模板有 {active} 个活跃实例，无法修改步骤。请等待实例完成或取消后再修改。",
            )
        orders = sorted(s.step_order for s in request.steps)
        if orders != list(range(1, len(request.steps) + 1)):
            raise HTTPException(status_code=422, detail="步骤序号必须从 1 连续递增")
        tpl.steps = [s.model_dump() for s in request.steps]
    db.commit()
    db.refresh(tpl)
    await pair_ws_manager.broadcast_to_admins({"event": "chains_changed"})
    return _template_to_dict(tpl)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(ChainTemplate).filter(ChainTemplate.id == template_id)
    if role != "admin":
        query = query.filter(ChainTemplate.user_id == user_id)
    tpl = query.first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    active = db.query(ChainInstance).filter(
        ChainInstance.template_id == template_id,
        ChainInstance.status.in_(["pending", "running"]),
    ).count()
    if active > 0:
        raise HTTPException(status_code=400, detail=f"该模板有 {active} 个活跃实例，无法删除")
    db.delete(tpl)
    db.commit()
    await pair_ws_manager.broadcast_to_admins({"event": "chains_changed"})
    return {"deleted": True, "id": template_id}


# --- Chain Instance Management ---

@router.post("/instances")
async def create_instances(
    request: ChainInstanceCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    from app.services.chain_service import chain_service

    user_id, role = user
    account_ids = list(request.account_ids or [])
    if request.group_ids:
        group_accounts = chain_service.resolve_accounts_from_groups(db, request.group_ids, user_id=None if role == "admin" else user_id)
        account_ids = list(set(account_ids + group_accounts))

    if not account_ids:
        raise HTTPException(status_code=422, detail="未指定任何账号")

    try:
        results = chain_service.create_chain_instances(db, request.template_id, account_ids, device_id=request.device_id, user_id=user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await pair_ws_manager.broadcast_to_admins({"event": "chains_changed"})
    return {
        "created_count": len(results["created"]),
        "skipped_busy_count": len(results["skipped_busy"]),
        "skipped_error_count": len(results["skipped_error"]),
        "created": results["created"],
        "skipped_busy": results["skipped_busy"],
        "skipped_error": results["skipped_error"],
    }


@router.get("/instances")
def list_instances(
    template_id: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(ChainInstance)
    if template_id:
        query = query.filter(ChainInstance.template_id == template_id)
    if account_id:
        query = query.filter(ChainInstance.account_id == account_id)
    if status:
        query = query.filter(ChainInstance.status == status)
    user_id, role = user
    if role != "admin":
        query = query.filter(ChainInstance.user_id == user_id)
    total = query.count()
    instances = query.order_by(ChainInstance.created_at.desc()).offset(skip).limit(limit).all()

    template_ids = list(set(i.template_id for i in instances))
    account_ids = list(set(i.account_id for i in instances))
    device_ids = list(set(i.device_id for i in instances if i.device_id))
    templates = {t.id: t.name for t in db.query(ChainTemplate).filter(ChainTemplate.id.in_(template_ids)).all()}
    accounts = {a.id: a.nickname for a in db.query(Account).filter(Account.id.in_(account_ids)).all()}
    devices_map = {d.id: d.name for d in db.query(Device).filter(Device.id.in_(device_ids)).all()} if device_ids else {}

    return {
        "instances": [
            _instance_to_dict(i, templates.get(i.template_id, ""), accounts.get(i.account_id, ""), devices_map.get(i.device_id, ""))
            for i in instances
        ],
        "total": total,
    }


@router.get("/instances/{instance_id}")
def get_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(ChainInstance).filter(ChainInstance.id == instance_id)
    if role != "admin":
        query = query.filter(ChainInstance.user_id == user_id)
    inst = query.first()
    if not inst:
        raise HTTPException(status_code=404, detail="链实例不存在")
    template = db.query(ChainTemplate).filter(ChainTemplate.id == inst.template_id).first()
    account = db.query(Account).filter(Account.id == inst.account_id).first()
    device = db.query(Device).filter(Device.id == inst.device_id).first() if inst.device_id else None

    tasks = (
        db.query(DBTask)
        .filter(DBTask.chain_instance_id == instance_id)
        .order_by(DBTask.step_order)
        .all()
    )

    result = _instance_to_dict(inst, template.name if template else "", account.nickname if account else "", device.name if device else "")
    result["tasks"] = [
        {
            "id": t.id,
            "step_order": t.step_order,
            "type": t.type,
            "status": t.status,
            "params": t.params,
            "result": t.result,
            "started_at": str(t.started_at) if t.started_at else None,
            "completed_at": str(t.completed_at) if t.completed_at else None,
        }
        for t in tasks
    ]
    return result


@router.post("/instances/{instance_id}/cancel")
async def cancel_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    query = db.query(ChainInstance).filter(ChainInstance.id == instance_id)
    if role != "admin":
        query = query.filter(ChainInstance.user_id == user_id)
    inst = query.first()
    if not inst:
        raise HTTPException(status_code=404, detail="链实例不存在")
    if inst.status in ("completed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"链实例已处于 {inst.status} 状态")

    # Cancel ALL pending/running tasks for this chain instance
    active_tasks = (
        db.query(DBTask)
        .filter(
            DBTask.chain_instance_id == instance_id,
            DBTask.status.in_(["pending", "running"]),
        )
        .all()
    )
    for task in active_tasks:
        task.status = "cancelled"
        task.completed_at = bj_now()

        if task.device_id:
            await pair_ws_manager.send_to_device(task.device_id, {
                "event": "cancel_task",
                "task_id": task.id,
            })

    inst.status = "cancelled"
    inst.completed_at = bj_now()
    db.commit()

    await pair_ws_manager.broadcast_to_admins({"event": "chains_changed"})
    return {"status": "cancelled", "id": instance_id}


@router.post("/instances/{instance_id}/retry")
async def retry_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    from app.services.chain_service import chain_service

    user_id, role = user
    query = db.query(ChainInstance).filter(ChainInstance.id == instance_id)
    if role != "admin":
        query = query.filter(ChainInstance.user_id == user_id)
    inst = query.first()
    if not inst:
        raise HTTPException(status_code=404, detail="链实例不存在")
    if inst.status != "failed":
        raise HTTPException(status_code=400, detail="只能重试失败的链实例")

    if chain_service.is_account_busy(db, inst.account_id):
        raise HTTPException(status_code=400, detail="该账号当前有其他任务在执行")

    failed_task = (
        db.query(DBTask)
        .filter(DBTask.chain_instance_id == instance_id, DBTask.status == "failed")
        .order_by(DBTask.step_order)
        .first()
    )
    if not failed_task:
        raise HTTPException(status_code=400, detail="未找到失败的步骤")

    failed_task.status = "pending"
    failed_task.device_id = None
    failed_task.started_at = None
    failed_task.completed_at = None
    failed_task.result = None

    inst.status = "running"
    inst.current_step = failed_task.step_order
    inst.completed_at = None
    db.commit()

    chain_service._safe_push_step_task(db, inst)

    await pair_ws_manager.broadcast_to_admins({"event": "chains_changed"})
    return {"status": "retrying", "id": instance_id, "step": failed_task.step_order}
