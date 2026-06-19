"""Chain template and instance orchestration use cases."""

from app.config import bj_now
from app.db_models import Account, ChainInstance, ChainTemplate, Device, Task as DBTask

from .adapters import chain_service
from .read_models import chain_instance_to_dict, chain_template_to_dict


class StepOrderError(ValueError):
    pass


class ActiveInstancesError(ValueError):
    pass


class NoAccountsError(ValueError):
    pass


class InvalidStateError(ValueError):
    pass


def create_template(db, request, user_id: str) -> dict:
    _validate_step_order(request.steps)
    template = ChainTemplate(
        name=request.name,
        description=request.description,
        steps=[step.model_dump() for step in request.steps],
        user_id=user_id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return chain_template_to_dict(template)


def list_templates(db, skip: int, limit: int, user: tuple) -> dict:
    limit = min(limit, 100)
    user_id, role = user
    query = db.query(ChainTemplate)
    if role != "admin":
        query = query.filter(ChainTemplate.user_id == user_id)
    total = query.count()
    templates = query.order_by(ChainTemplate.created_at.desc()).offset(skip).limit(limit).all()
    return {"templates": [chain_template_to_dict(template) for template in templates], "total": total}


def get_template(db, template_id: str, user: tuple) -> dict:
    template = _template_query(db, template_id, user).first()
    if not template:
        raise LookupError("模板不存在")
    return chain_template_to_dict(template)


def update_template(db, template_id: str, request, user: tuple) -> dict:
    template = _template_query(db, template_id, user).first()
    if not template:
        raise LookupError("模板不存在")
    if request.name is not None:
        template.name = request.name
    if request.description is not None:
        template.description = request.description
    if request.steps is not None:
        active_count = db.query(ChainInstance).filter(
            ChainInstance.template_id == template_id,
            ChainInstance.status.in_(["pending", "running"]),
        ).count()
        if active_count > 0:
            raise ActiveInstancesError(f"该模板有 {active_count} 个活跃实例，无法修改步骤。请等待实例完成或取消后再修改。")
        _validate_step_order(request.steps)
        template.steps = [step.model_dump() for step in request.steps]
    db.commit()
    db.refresh(template)
    return chain_template_to_dict(template)


def delete_template(db, template_id: str, user: tuple) -> dict:
    template = _template_query(db, template_id, user).first()
    if not template:
        raise LookupError("模板不存在")
    active_count = db.query(ChainInstance).filter(
        ChainInstance.template_id == template_id,
        ChainInstance.status.in_(["pending", "running"]),
    ).count()
    if active_count > 0:
        raise ActiveInstancesError(f"该模板有 {active_count} 个活跃实例，无法删除")
    db.delete(template)
    db.commit()
    return {"deleted": True, "id": template_id}


def create_instances(db, request, user: tuple) -> dict:
    user_id, role = user
    account_ids = list(request.account_ids or [])
    if request.group_ids:
        group_accounts = chain_service.resolve_accounts_from_groups(
            db,
            request.group_ids,
            user_id=None if role == "admin" else user_id,
        )
        account_ids = list(set(account_ids + group_accounts))

    if not account_ids:
        raise NoAccountsError("未指定任何账号")

    try:
        results = chain_service.create_chain_instances(
            db,
            request.template_id,
            account_ids,
            device_id=request.device_id,
            user_id=user_id,
        )
    except ValueError as error:
        raise LookupError(str(error))

    return {
        "created_count": len(results["created"]),
        "skipped_busy_count": len(results["skipped_busy"]),
        "skipped_error_count": len(results["skipped_error"]),
        "created": results["created"],
        "skipped_busy": results["skipped_busy"],
        "skipped_error": results["skipped_error"],
    }


def list_instances(db, template_id: str, account_id: str, status: str, skip: int, limit: int, user: tuple) -> dict:
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

    template_ids = list({instance.template_id for instance in instances})
    account_ids = list({instance.account_id for instance in instances})
    device_ids = list({instance.device_id for instance in instances if instance.device_id})
    templates = {template.id: template.name for template in db.query(ChainTemplate).filter(ChainTemplate.id.in_(template_ids)).all()}
    accounts = {account.id: account.nickname for account in db.query(Account).filter(Account.id.in_(account_ids)).all()}
    devices = {device.id: device.name for device in db.query(Device).filter(Device.id.in_(device_ids)).all()} if device_ids else {}

    return {
        "instances": [
            chain_instance_to_dict(
                instance,
                templates.get(instance.template_id, ""),
                accounts.get(instance.account_id, ""),
                devices.get(instance.device_id, ""),
            )
            for instance in instances
        ],
        "total": total,
    }


def get_instance(db, instance_id: str, user: tuple) -> dict:
    instance = _instance_query(db, instance_id, user).first()
    if not instance:
        raise LookupError("链实例不存在")
    template = db.query(ChainTemplate).filter(ChainTemplate.id == instance.template_id).first()
    account = db.query(Account).filter(Account.id == instance.account_id).first()
    device = db.query(Device).filter(Device.id == instance.device_id).first() if instance.device_id else None

    tasks = (
        db.query(DBTask)
        .filter(DBTask.chain_instance_id == instance_id)
        .order_by(DBTask.step_order)
        .all()
    )

    result = chain_instance_to_dict(
        instance,
        template.name if template else "",
        account.nickname if account else "",
        device.name if device else "",
    )
    result["tasks"] = [
        {
            "id": task.id,
            "step_order": task.step_order,
            "type": task.type,
            "status": task.status,
            "params": task.params,
            "result": task.result,
            "started_at": str(task.started_at) if task.started_at else None,
            "completed_at": str(task.completed_at) if task.completed_at else None,
        }
        for task in tasks
    ]
    return result


def cancel_instance(db, instance_id: str, user: tuple) -> tuple[dict, list[tuple[str, str]]]:
    instance = _instance_query(db, instance_id, user).first()
    if not instance:
        raise LookupError("链实例不存在")
    if instance.status in ("completed", "cancelled"):
        raise InvalidStateError(f"链实例已处于 {instance.status} 状态")

    notifications = []
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
            notifications.append((task.device_id, task.id))

    instance.status = "cancelled"
    instance.completed_at = bj_now()
    db.commit()

    return {"status": "cancelled", "id": instance_id}, notifications


def retry_instance(db, instance_id: str, user: tuple) -> dict:
    instance = _instance_query(db, instance_id, user).first()
    if not instance:
        raise LookupError("链实例不存在")
    if instance.status != "failed":
        raise InvalidStateError("只能重试失败的链实例")

    if chain_service.is_account_busy(db, instance.account_id):
        raise InvalidStateError("该账号当前有其他任务在执行")

    failed_task = (
        db.query(DBTask)
        .filter(DBTask.chain_instance_id == instance_id, DBTask.status == "failed")
        .order_by(DBTask.step_order)
        .first()
    )
    if not failed_task:
        raise InvalidStateError("未找到失败的步骤")

    failed_task.status = "pending"
    failed_task.device_id = None
    failed_task.started_at = None
    failed_task.completed_at = None
    failed_task.result = None

    instance.status = "running"
    instance.current_step = failed_task.step_order
    instance.completed_at = None
    db.commit()

    chain_service._safe_push_step_task(db, instance)

    return {"status": "retrying", "id": instance_id, "step": failed_task.step_order}


def _validate_step_order(steps):
    orders = sorted(step.step_order for step in steps)
    if orders != list(range(1, len(steps) + 1)):
        raise StepOrderError("步骤序号必须从 1 连续递增")


def _template_query(db, template_id: str, user: tuple):
    user_id, role = user
    query = db.query(ChainTemplate).filter(ChainTemplate.id == template_id)
    if role != "admin":
        query = query.filter(ChainTemplate.user_id == user_id)
    return query


def _instance_query(db, instance_id: str, user: tuple):
    user_id, role = user
    query = db.query(ChainInstance).filter(ChainInstance.id == instance_id)
    if role != "admin":
        query = query.filter(ChainInstance.user_id == user_id)
    return query
