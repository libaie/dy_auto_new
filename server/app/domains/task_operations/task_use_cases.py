"""任务运营业务域模块。

任务运营业务域，负责任务参数解析、执行用例、实时事件和路由接口。本文件负责 task_use_cases 相关业务规则、状态转换和外部系统边界。
"""

from dataclasses import dataclass
import logging

from app.db.models import Account, AccountGroupMember, Channel, ChannelItem as DBChannelItem, Device
from app.models import TaskType as TT

from .adapters import channel_service, task_service
from .param_resolution import (
    maybe_expand_keywords,
    maybe_resolve_content_template,
    maybe_resolve_dm_sequence,
    maybe_resolve_nurture_subtask_templates,
    validate_and_normalize_params,
)
from .read_models import (
    batch_create_response,
    batch_delete_response,
    delete_response,
    task_list_response,
)

logger = logging.getLogger(__name__)


class TaskValidationError(ValueError):
    """业务类：承载 TaskValidationError 相关的数据结构、状态或业务协作。"""
    """A request is syntactically valid but cannot be processed."""


class TaskParamsError(ValueError):
    """业务类：承载 TaskParamsError 相关的数据结构、状态或业务协作。"""
    """Task params failed model validation."""


class TaskNotFoundError(LookupError):
    """业务类：承载 TaskNotFoundError 相关的数据结构、状态或业务协作。"""
    """Requested task does not exist."""


@dataclass(frozen=True)
class BatchCreateOutcome:
    """业务类：承载 BatchCreateOutcome 相关的数据结构、状态或业务协作。"""
    payload: dict
    notify_devices: bool
    notify_admins: bool


async def create_task(db, request, user):
    """业务函数：处理 create_task 对应的业务流程、校验或数据转换。"""
    if not request.account_id:
        raise TaskValidationError("account_id is required for single create")

    params = await _resolve_params_for_request(db, request.type.value, request.params)

    try:
        user_id, _ = user
        return task_service.create_task(
            db=db,
            task_type=request.type,
            account_id=request.account_id,
            params=params,
            device_id=request.device_id or None,
            user_id=user_id,
        )
    except ValueError as e:
        raise TaskValidationError(str(e)) from e


async def batch_create_tasks(db, request, user) -> BatchCreateOutcome:
    """业务函数：处理 batch_create_tasks 对应的业务流程、校验或数据转换。"""
    if not request.group_ids and not request.account_ids:
        raise TaskValidationError("需要提供 group_ids 或 account_ids")

    user_id, _ = user
    ttype = request.type.value
    params = await _resolve_params_for_request(db, ttype, request.params)
    keywords = _keywords_from_params(params)

    _needs_keywords = ttype in {"search_comment", "search_like", "search_dm", "reply_comment", "collect"}
    _has_share_links = bool(params.get("share_links"))
    if _needs_keywords and not keywords and not request.params.get("keyword") and not _has_share_links:
        raise TaskValidationError("关键词不能为空（采集任务可使用分享链接代替）")

    max_keywords = 500
    if len(keywords) > max_keywords:
        raise TaskValidationError(f"关键词最多 {max_keywords} 个，当前 {len(keywords)} 个")

    _assert_groups_exist(db, request.group_ids)
    all_accounts = _resolve_active_accounts(db, request.group_ids, request.account_ids)
    if not all_accounts:
        raise TaskValidationError("所选分组/账号没有活跃账号，请先添加活跃账号")

    if keywords:
        created_tasks = _create_channel_tasks(db, request, user_id, ttype, params, keywords, all_accounts)
        mode = "channel"
    else:
        created_tasks = _create_direct_tasks(db, request, user_id, ttype, params, all_accounts)
        mode = "direct"

    db.commit()

    notify_devices = _should_notify_devices_for_created_tasks(db, created_tasks)
    return BatchCreateOutcome(
        payload=batch_create_response(len(created_tasks), mode),
        notify_devices=notify_devices,
        notify_admins=bool(created_tasks),
    )


def list_tasks(db, status, task_type, search, sort_by, sort_order, skip, limit, user) -> dict:
    """业务函数：处理 list_tasks 对应的业务流程、校验或数据转换。"""
    limit = min(limit, 100)
    user_id, role = user
    current_user_id = None if role == "admin" else user_id
    tasks = task_service.list_tasks(
        db=db,
        status=status,
        task_type=task_type,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit,
        current_user_id=current_user_id,
    )
    total = task_service.count_tasks(
        db=db,
        status=status,
        task_type=task_type,
        search=search,
        current_user_id=current_user_id,
    )
    return task_list_response(tasks, total)


def batch_delete_tasks(db, task_ids: list[str]) -> dict:
    """业务函数：处理 batch_delete_tasks 对应的业务流程、校验或数据转换。"""
    return batch_delete_response(task_service.delete_tasks_batch(db, task_ids))


def get_task(db, task_id: str):
    """业务函数：处理 get_task 对应的业务流程、校验或数据转换。"""
    task = task_service.get_task(db=db, task_id=task_id)
    if not task:
        raise TaskNotFoundError("Task not found")
    return task


def cancel_task(db, task_id: str):
    """业务函数：处理 cancel_task 对应的业务流程、校验或数据转换。"""
    try:
        return task_service.cancel_task(db=db, task_id=task_id)
    except ValueError as e:
        if "not found" in str(e):
            raise TaskNotFoundError("Task not found") from e
        raise TaskValidationError(str(e)) from e


def delete_task(db, task_id: str) -> dict:
    """业务函数：处理 delete_task 对应的业务流程、校验或数据转换。"""
    try:
        task_service.delete_task(db=db, task_id=task_id)
    except ValueError as e:
        if "not found" in str(e):
            raise TaskNotFoundError("Task not found") from e
        raise TaskValidationError(str(e)) from e
    return delete_response(task_id)


async def _resolve_params_for_request(db, task_type: str, params: dict) -> dict:
    """业务函数：处理 _resolve_params_for_request 对应的业务流程、校验或数据转换。"""
    try:
        resolved = validate_and_normalize_params(task_type, params)
    except Exception as e:
        raise TaskParamsError(f"Invalid params for {task_type}: {str(e)}") from e

    resolved = await maybe_resolve_content_template(resolved, task_type, db=db)
    resolved = await maybe_resolve_dm_sequence(resolved, db=db)
    resolved = await maybe_expand_keywords(resolved, task_type, db=db)
    return maybe_resolve_nurture_subtask_templates(resolved, task_type, db=db)


def _keywords_from_params(params: dict) -> list[str]:
    """业务函数：处理 _keywords_from_params 对应的业务流程、校验或数据转换。"""
    raw_keywords = params.get("keywords", []) or ([params.get("keyword")] if params.get("keyword") else [])
    return [k.strip() for k in raw_keywords if k and k.strip()]


def _assert_groups_exist(db, group_ids: list[str]):
    """业务函数：处理 _assert_groups_exist 对应的业务流程、校验或数据转换。"""
    if not group_ids:
        return

    from app.db.models import AccountGroup

    existing_groups = db.query(AccountGroup.id).filter(
        AccountGroup.id.in_(group_ids)
    ).all()
    existing_ids = {g[0] for g in existing_groups}
    missing = [gid for gid in group_ids if gid not in existing_ids]
    if missing:
        raise TaskValidationError(f"分组不存在: {', '.join(missing[:3])}")


def _resolve_active_accounts(db, group_ids: list[str], account_ids: list[str]) -> list:
    """业务函数：处理 _resolve_active_accounts 对应的业务流程、校验或数据转换。"""
    all_accounts = []
    seen_account_ids = set()

    for gid in group_ids:
        member_account_ids = db.query(AccountGroupMember.account_id).filter(
            AccountGroupMember.group_id == gid
        ).scalar_subquery()
        accounts = db.query(Account).filter(
            Account.id.in_(member_account_ids),
            Account.status == "active",
        ).all()
        for acc in accounts:
            if acc.id not in seen_account_ids:
                seen_account_ids.add(acc.id)
                all_accounts.append(acc)

    for aid in account_ids:
        if aid in seen_account_ids:
            continue
        acc = db.query(Account).filter(
            Account.id == aid, Account.status == "active"
        ).first()
        if acc:
            seen_account_ids.add(acc.id)
            all_accounts.append(acc)

    return all_accounts


def _create_channel_tasks(db, request, user_id: str, ttype: str, params: dict, keywords: list[str], all_accounts: list) -> list[dict]:
    """业务函数：处理 _create_channel_tasks 对应的业务流程、校验或数据转换。"""
    channel_group_id = _resolve_channel_group_id(db, request, all_accounts)
    template_params = {k: v for k, v in params.items() if k not in ("keyword", "keywords")}
    channel = Channel(
        group_id=channel_group_id,
        task_type=ttype,
        status="active",
        account_mode="round_robin",
        params_template=template_params,
        user_id=user_id,
    )
    db.add(channel)
    db.flush()

    assigned_ids = channel_service._round_robin_assign(db, keywords, all_accounts)
    created_tasks = []
    qpos = 0
    for idx, kw in enumerate(keywords):
        channel_item = DBChannelItem(
            channel_id=channel.id,
            keyword=kw.strip(),
            account_id=assigned_ids[idx],
            status="pending",
            queue_position=qpos,
        )
        qpos += 1
        db.add(channel_item)
        created_tasks.append({"keyword": kw.strip(), "account_id": assigned_ids[idx]})
    logger.info(
        "通道 %s 已创建: %d 关键词 × %d 账号 (轮询) = %d 项",
        channel.id,
        len(keywords),
        len(all_accounts),
        len(created_tasks),
    )
    return created_tasks


def _resolve_channel_group_id(db, request, all_accounts: list) -> str:
    """业务函数：处理 _resolve_channel_group_id 对应的业务流程、校验或数据转换。"""
    channel_group_id = request.group_ids[0] if request.group_ids else None
    if channel_group_id:
        return channel_group_id

    member_group = db.query(AccountGroupMember.group_id).filter(
        AccountGroupMember.account_id.in_(request.account_ids)
    ).first()
    if member_group:
        return member_group[0]

    from app.db.models import AccountGroup
    from datetime import datetime as dt

    display = all_accounts[0].nickname or all_accounts[0].douyin_id or all_accounts[0].id[:8]
    ts = dt.now().strftime("%m%d%H%M%S")
    max_display = 100 - len(f"自动分组--{ts}") - 1
    if len(display) > max_display:
        display = display[:max_display]
    account_group = AccountGroup(
        name=f"自动分组-{display}-{ts}",
        description="系统自动创建（单账号批量任务）",
    )
    db.add(account_group)
    db.flush()
    for acc in all_accounts:
        db.add(AccountGroupMember(group_id=account_group.id, account_id=acc.id))
    db.flush()
    return account_group.id


def _create_direct_tasks(db, request, user_id: str, ttype: str, params: dict, all_accounts: list) -> list[dict]:
    """业务函数：处理 _create_direct_tasks 对应的业务流程、校验或数据转换。"""
    created_tasks = []
    for acc in all_accounts:
        task = task_service.create_task(
            db=db,
            task_type=TT(ttype),
            account_id=acc.id,
            params=params,
            device_id=request.device_id or None,
            user_id=user_id,
        )
        created_tasks.append({"id": task.id, "account_id": acc.id})
    return created_tasks


def _should_notify_devices_for_created_tasks(db, created_tasks: list[dict]) -> bool:
    """业务函数：处理 _should_notify_devices_for_created_tasks 对应的业务流程、校验或数据转换。"""
    if not created_tasks:
        return False
    if not any(task.get("id") for task in created_tasks):
        return True

    unbound_accounts = [
        task["account_id"] for task in created_tasks if task.get("id")
        if not db.query(Device).filter(Device.bound_account_id == task["account_id"]).first()
    ]
    return bool(unbound_accounts)
