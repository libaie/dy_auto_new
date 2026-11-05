"""Task management CRUD API — admin only."""
import logging

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token, get_owned_resource, require_resource_owner, resource_user_ids
from app.db_models import Task as DBTask, Account, Device, AccountGroup, AccountGroupMember
from app.config import bj_now
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
    account_ids: list[str] = []
    device_id: Optional[str] = None
    params: dict = {}


async def _maybe_resolve_content_template(params: dict, task_type: str, db=None) -> dict:
    """If params has content_template_id, resolve it into params.content."""
    template_id = params.get("content_template_id")
    if not template_id:
        return params
    try:
        keyword = params.get("keyword") or (params.get("keywords", [None])[0]) or ""
        context = {"keyword": keyword, "task_type": task_type}
        generated = await content_service.generate_from_template(db, template_id, context)
        params["content"] = generated
        logger.info("Resolved content_template_id=%s for task_type=%s", template_id, task_type)
    except Exception as e:
        logger.warning("Failed to resolve content_template_id=%s: %s", template_id, e)
    return params


async def _maybe_resolve_dm_sequence(params: dict, db=None) -> dict:
    """If params has dm_sequence_id, resolve into inline dm_messages + content.
    Keeps dm_sequence_id so device can look up poll cache for variants.
    Inline dm_messages serves as fallback for old devices or cache miss."""
    seq_id = params.get("dm_sequence_id")
    if not seq_id or not db:
        return params
    try:
        from app.db_models import DMSequence
        seq = db.query(DMSequence).filter(DMSequence.id == seq_id).first()
        if seq and seq.messages:
            params["dm_messages"] = seq.messages
            # Fallback: first message content for old devices
            first = seq.messages[0]
            if isinstance(first, dict):
                params["content"] = first.get("content", "")
            logger.info("Resolved dm_sequence_id=%s into %d inline messages (id preserved for variants)", seq_id, len(seq.messages))
        else:
            logger.warning("dm_sequence_id=%s not found in DB, removing from params", seq_id)
            params.pop("dm_sequence_id", None)
    except Exception as e:
        logger.warning("Failed to resolve dm_sequence_id=%s: %s", seq_id, e)
        params.pop("dm_sequence_id", None)
    return params


async def _maybe_expand_keywords(params: dict, task_type: str, db=None) -> dict:
    """If nurture task has keywords (seed), expand them into keyword_matrix via AI."""
    if task_type != "nurture" or "keywords" not in params:
        return params
    seeds = [k.strip() for k in params.get("keywords", []) if k and k.strip()]
    if not seeds:
        return params
    existing_matrix = [k.strip() for k in params.get("keyword_matrix", []) if k and k.strip()]
    if existing_matrix:
        params["keyword_matrix"] = list(dict.fromkeys(seeds + existing_matrix))
        return params
    try:
        all_expanded = []
        for seed in seeds[:3]:
            expand_count = int(params.get("expand_count", 8))
            expanded = await content_service.generate_keyword_matrix(seed, expand_count, db=db)
            all_expanded.extend(expanded)
        unique = list(dict.fromkeys(seeds + all_expanded))
        params["keyword_matrix"] = unique
        for kw in all_expanded:
            logger.info("AI expanded keyword: %s", kw)
    except Exception as e:
        logger.warning("Failed to expand keywords for nurture task: %s", e)
    return params


def _maybe_resolve_nurture_subtask_templates(params: dict, task_type: str, db=None) -> dict:
    if task_type != "nurture" or not db:
        return params
    sub_tasks = params.get("sub_tasks")
    if not isinstance(sub_tasks, list):
        return params
    keyword = params.get("keyword") or ""
    if not keyword:
        keywords = params.get("keywords") or params.get("keyword_matrix") or []
        if keywords:
            keyword = keywords[0]
    for sub_task in sub_tasks:
        if not isinstance(sub_task, dict) or sub_task.get("type") != "comment":
            continue
        template_id = sub_task.get("content_template_id")
        if not template_id or sub_task.get("content"):
            continue
        try:
            tpl_body = content_service.get_template_body(db, template_id)
            if tpl_body:
                sub_task["content"] = content_service.substitute_variables(
                    tpl_body, {"keyword": keyword}
                )
        except Exception as e:
            logger.warning("Failed to resolve nurture sub_task template=%s: %s", template_id, e)
    return params


def _resolve_task_type(type_val) -> TaskType:
    if isinstance(type_val, TaskType):
        return type_val
    return TaskType(type_val)


def _validate_and_normalize_params(task_type: str, params: dict) -> dict:
    """Validate and normalize task params using models.TASK_PARAMS_VALIDATORS."""
    from app.models import TASK_PARAMS_VALIDATORS
    from pydantic import BaseModel as PydanticBase

    validator = TASK_PARAMS_VALIDATORS.get(task_type)
    if validator is None:
        return params  # unknown type, passthrough

    if callable(validator) and not isinstance(validator, type):
        # Function-style validator (e.g. _validate_nurture_params)
        return validator(params)
    elif isinstance(validator, type) and issubclass(validator, PydanticBase):
        # Pydantic model validator
        validated = validator(**params)
        return validated.model_dump(exclude_none=True)
    return params


@router.post("")
async def create_task(
    request: TaskCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    if not request.account_id:
        raise HTTPException(status_code=400, detail="account_id is required for single create")
    get_owned_resource(db, Account, request.account_id, user)
    if request.device_id:
        get_owned_resource(db, Device, request.device_id, user)
    try:
        params = _validate_and_normalize_params(request.type.value, request.params)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid params for {request.type.value}: {str(e)}")
    params = await _maybe_resolve_content_template(params, request.type.value, db=db)
    params = await _maybe_resolve_dm_sequence(params, db=db)
    params = await _maybe_expand_keywords(params, request.type.value, db=db)
    params = _maybe_resolve_nurture_subtask_templates(params, request.type.value, db=db)

    try:
        user_id, _ = user
        task = task_service.create_task(
            db=db,
            task_type=request.type,
            account_id=request.account_id,
            params=params,
            device_id=request.device_id or None,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})
    await pair_ws_manager.broadcast_to_admins({
        "event": "task_updated",
        "task_id": task.id,
        "status": "pending",
    }, user_ids=resource_user_ids(db, DBTask, task.id))
    return task


@router.post("/batch")
async def batch_create_tasks(
    request: TaskBatchCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    if not request.group_ids and not request.account_ids:
        raise HTTPException(status_code=400, detail="需要提供 group_ids 或 account_ids")
    user_id, role = user
    # Validate the entire selection before any generation or mutation.
    for account_id in request.account_ids:
        get_owned_resource(db, Account, account_id, user)
    for group_id in request.group_ids:
        get_owned_resource(db, AccountGroup, group_id, user)
        group_accounts = db.query(Account).join(AccountGroupMember, AccountGroupMember.account_id == Account.id).filter(
            AccountGroupMember.group_id == group_id
        ).all()
        for account in group_accounts:
            require_resource_owner(account, user)
    if request.device_id:
        get_owned_resource(db, Device, request.device_id, user)
    ttype = request.type.value

    try:
        params = _validate_and_normalize_params(ttype, request.params)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid params for {ttype}: {str(e)}")

    from app.db_models import Channel, ChannelItem as DBChannelItem
    from app.models import TaskType as TT

    params = await _maybe_resolve_content_template(params, ttype, db=db)
    params = await _maybe_resolve_dm_sequence(params, db=db)
    params = await _maybe_expand_keywords(params, ttype, db=db)
    params = _maybe_resolve_nurture_subtask_templates(params, ttype, db=db)
    raw_keywords = params.get("keywords", []) or ([params.get("keyword")] if params.get("keyword") else [])
    keywords = [k.strip() for k in raw_keywords if k and k.strip()]

    # Only require keywords for keyword-based task types (those with a params validator)
    # collect 允许只用 share_links (分享链接采集)，不需要 keyword
    _needs_keywords = ttype in {"search_comment", "search_like", "search_dm", "reply_comment", "collect"}
    _has_share_links = bool(params.get("share_links"))
    if _needs_keywords and not keywords and not request.params.get("keyword") and not _has_share_links:
        raise HTTPException(status_code=400, detail="关键词不能为空（采集任务可使用分享链接代替）")

    # 关键词数量上限
    MAX_KEYWORDS = 500
    if len(keywords) > MAX_KEYWORDS:
        raise HTTPException(status_code=400, detail=f"关键词最多 {MAX_KEYWORDS} 个，当前 {len(keywords)} 个")

    # 校验 group_ids 存在性（避免 FK 约束异常）
    if request.group_ids:
        existing_groups = db.query(AccountGroup.id).filter(
            AccountGroup.id.in_(request.group_ids)
        ).all()
        existing_ids = {g[0] for g in existing_groups}
        missing = [gid for gid in request.group_ids if gid not in existing_ids]
        if missing:
            raise HTTPException(status_code=400, detail=f"分组不存在: {', '.join(missing[:3])}")

    # Resolve accounts: from group_ids + from account_ids
    all_accounts = []
    seen_account_ids = set()

    for gid in request.group_ids:
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

    for aid in request.account_ids:
        if aid in seen_account_ids:
            continue
        acc = db.query(Account).filter(
            Account.id == aid, Account.status == "active"
        ).first()
        if acc:
            seen_account_ids.add(acc.id)
            all_accounts.append(acc)

    if not all_accounts:
        raise HTTPException(status_code=400, detail="所选分组/账号没有活跃账号，请先添加活跃账号")

    created_tasks = []
    if keywords:
        # 确定通道归属的分组：优先用 group_ids[0]，否则查账号所属分组
        channel_group_id = request.group_ids[0] if request.group_ids else None
        if not channel_group_id:
            # 从 account_ids 中查所属分组
            member_group_query = db.query(AccountGroupMember.group_id).join(
                AccountGroup, AccountGroup.id == AccountGroupMember.group_id
            ).filter(AccountGroupMember.account_id.in_(request.account_ids))
            if role != "admin":
                member_group_query = member_group_query.filter(AccountGroup.user_id == user_id)
            member_group = member_group_query.first()
            if member_group:
                channel_group_id = member_group[0]
            else:
                # 账号不在任何分组中，自动创建分组
                display = all_accounts[0].nickname or all_accounts[0].douyin_id or all_accounts[0].id[:8]
                # name 字段 String(100)，截断 display 确保不超长
                ts = bj_now().strftime('%m%d%H%M%S')
                max_display = 100 - len(f"自动分组--{ts}") - 1  # 预留截断空间
                if len(display) > max_display:
                    display = display[:max_display]
                ag = AccountGroup(
                    name=f"自动分组-{display}-{ts}",
                    description="系统自动创建（单账号批量任务）",
                    user_id=user_id,
                )
                db.add(ag)
                db.flush()
                channel_group_id = ag.id
                # 将账号加入新分组
                for acc in all_accounts:
                    db.add(AccountGroupMember(group_id=ag.id, account_id=acc.id))
                db.flush()

        # 总是新建通道（UUID 自动生成），不复用旧通道
        template_params = {k: v for k, v in params.items() if k not in ("keyword", "keywords")}
        ch = Channel(
            group_id=channel_group_id,
            task_type=ttype,
            status="active",
            account_mode="round_robin",
            params_template=template_params,
            user_id=user_id,
        )
        db.add(ch)
        db.flush()

        # 轮询分配：每个关键词只分配给一个账号，多账号交叉领取
        from app.services.channel_service import channel_service as _ch_svc
        assigned_ids = _ch_svc._round_robin_assign(db, keywords, all_accounts)
        qpos = 0
        for idx, kw in enumerate(keywords):
            ci = DBChannelItem(
                channel_id=ch.id,
                keyword=kw.strip(),
                account_id=assigned_ids[idx],
                status="pending",
                queue_position=qpos,
            )
            qpos += 1
            db.add(ci)
            created_tasks.append({"keyword": kw.strip(), "account_id": assigned_ids[idx]})
        logger.info("通道 %s 已创建: %d 关键词 × %d 账号 (轮询) = %d 项",
                     ch.id, len(keywords), len(all_accounts), len(created_tasks))
    else:
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

    db.commit()

    if created_tasks:
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
        # 通知前端更新任务列表
        await pair_ws_manager.broadcast_to_admins({"event": "tasks_changed"}, user_ids=[user_id] if user_id else [])

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
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    user_id, role = user
    tasks = task_service.list_tasks(db=db, status=status, task_type=type, search=search,
                                     sort_by=sort_by, sort_order=sort_order, skip=skip, limit=limit,
                                     current_user_id=None if role == "admin" else user_id)
    total = task_service.count_tasks(db=db, status=status, task_type=type, search=search,
                                     current_user_id=None if role == "admin" else user_id)
    return {"tasks": tasks, "total": total}


class BatchDeleteRequest(BaseModel):
    task_ids: list[str]


@router.post("/batch-delete")
async def batch_delete_tasks(
    body: BatchDeleteRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    # Authorize every existing row first so mixed batches cannot partially mutate.
    owners = set()
    for task in db.query(DBTask).filter(DBTask.id.in_(body.task_ids)).all():
        require_resource_owner(task, user, "Task not found")
        if task.user_id:
            owners.add(task.user_id)
    count = task_service.delete_tasks_batch(db, body.task_ids)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_admins({"event": "tasks_changed"}, user_ids=list(owners))
    return {"deleted": count}


@router.get("/{task_id}")
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    get_owned_resource(db, DBTask, task_id, user)
    task = task_service.get_task(db=db, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    owned_task = get_owned_resource(db, DBTask, task_id, user)
    owner_ids = [owned_task.user_id] if owned_task.user_id else []
    try:
        task = task_service.cancel_task(db=db, task_id=task_id)
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail="Task not found")
        raise HTTPException(status_code=400, detail=str(e))

    from app.ws_manager import pair_ws_manager

    if task.device_id:
        await pair_ws_manager.send_to_device(task.device_id, {
            "event": "cancel_task",
            "task_id": task.id,
        })

    # Broadcast so other devices know a channel item is now available
    await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})
    # 通知前端任务列表更新
    await pair_ws_manager.broadcast_to_admins({
        "event": "task_updated",
        "task_id": task.id,
        "status": "cancelled",
    }, user_ids=owner_ids)

    return task


@router.delete("/{task_id}")
async def delete_task(task_id: str, db=Depends(get_db), user=Depends(verify_admin_token)):
    task = get_owned_resource(db, DBTask, task_id, user)
    owner_ids = [task.user_id] if task.user_id else []
    try:
        task_service.delete_task(db=db, task_id=task_id)
    except ValueError as e:
        if "not found" in str(e): raise HTTPException(status_code=404, detail="Task not found")
        raise HTTPException(status_code=400, detail=str(e))
    # 通知前端
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_admins({"event": "tasks_changed"}, user_ids=owner_ids)
    return {"deleted": True, "task_id": task_id}
