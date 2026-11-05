"""Channel management API -- admin endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token, require_role, resource_user_ids
from app.models import (
    ChannelCreate, ChannelUpdate, ChannelAppendItems,
    ChannelItemUpdate, ChannelEditRequest, ChannelItemEditRequest, BatchEditRequest,
)
from app.services.channel_service import channel_service
from app.ws_manager import pair_ws_manager
from app.db_models import Account, AccountGroup, ChannelItem, Device, Channel

router = APIRouter(prefix="/api/channels", tags=["channels"])


def _item_owner_ids(db: Session, item_ids: list[str], user: tuple) -> list[str]:
    query = db.query(Channel.user_id).join(ChannelItem, ChannelItem.channel_id == Channel.id).filter(
        ChannelItem.id.in_(item_ids)
    )
    if user[1] != "admin":
        query = query.filter(Channel.user_id == user[0])
    return list({owner_id for (owner_id,) in query.all() if owner_id})


def _channel_to_response(ch, stats: dict, group_name: str = "") -> dict:
    return {
        "id": ch.id,
        "group_id": ch.group_id,
        "group_name": group_name,
        "task_type": ch.task_type,
        "status": ch.status,
        "account_mode": ch.account_mode,
        "account_id": ch.account_id or "",
        "params_template": ch.params_template or {},
        "cooldown_seconds": ch.cooldown_seconds,
        "delay_range": ch.delay_range or [3000, 8000],
        "total": stats["total"],
        "pending": stats["pending"],
        "assigned": stats["assigned"],
        "completed": stats["completed"],
        "failed": stats["failed"],
        "skipped": stats["skipped"],
        "created_at": str(ch.created_at) if ch.created_at else None,
        "completed_at": str(ch.completed_at) if ch.completed_at else None,
    }


def _item_to_response(item, account_nickname: str = "", device_name: str = "") -> dict:
    return {
        "id": item.id,
        "keyword": item.keyword,
        "account_id": item.account_id,
        "account_nickname": account_nickname,
        "status": item.status,
        "assigned_device_id": item.assigned_device_id or "",
        "device_name": device_name,
        "task_id": item.task_id or "",
        "queue_position": item.queue_position,
        "created_at": str(item.created_at) if item.created_at else None,
        "completed_at": str(item.completed_at) if item.completed_at else None,
    }


@router.post("")
async def create_channel(
    request: ChannelCreate,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    try:
        user_id, _ = user
        ch = channel_service.create_channel(
            db,
            group_id=request.group_id,
            task_type=request.task_type.value,
            account_mode=request.account_mode,
            keywords=request.keywords,
            params_template=request.params_template,
            account_id=request.account_id,
            cooldown_seconds=request.cooldown_seconds,
            delay_range=request.delay_range,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"}, user_ids=resource_user_ids(db, Channel, ch.id))
    group = db.query(AccountGroup).filter(AccountGroup.id == ch.group_id).first()
    stats = channel_service.get_channel_stats(db, ch.id)
    return _channel_to_response(ch, stats, group.name if group else "")


@router.get("")
def list_channels(
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    channels = channel_service.list_channels(db, user_id=scope_user_id)
    group_ids = list(set(ch.group_id for ch in channels))
    groups = {
        g.id: g.name
        for g in db.query(AccountGroup).filter(AccountGroup.id.in_(group_ids)).all()
    } if group_ids else {}

    channel_ids = [ch.id for ch in channels]
    stats_map = channel_service.get_channels_stats_batch(db, channel_ids)

    result = []
    for ch in channels:
        stats = stats_map.get(ch.id, {"total": 0, "pending": 0, "assigned": 0, "completed": 0, "failed": 0, "skipped": 0})
        result.append(_channel_to_response(ch, stats, groups.get(ch.group_id, "")))
    return {"channels": result, "total": len(result)}


@router.get("/{channel_id}")
def get_channel(
    channel_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    ch = channel_service.get_channel(db, channel_id, user_id=scope_user_id)
    if not ch:
        raise HTTPException(status_code=404, detail="通道不存在")

    group = db.query(AccountGroup).filter(AccountGroup.id == ch.group_id).first()
    stats = channel_service.get_channel_stats(db, ch.id)
    resp = _channel_to_response(ch, stats, group.name if group else "")

    items = db.query(ChannelItem).filter(ChannelItem.channel_id == channel_id).order_by(ChannelItem.queue_position).all()
    account_ids = list(set(i.account_id for i in items))
    device_ids = list(set(i.assigned_device_id for i in items if i.assigned_device_id))
    accounts = {a.id: a.nickname for a in db.query(Account).filter(Account.id.in_(account_ids)).all()} if account_ids else {}
    devices_map = {d.id: d.name for d in db.query(Device).filter(Device.id.in_(device_ids)).all()} if device_ids else {}

    resp["items"] = [
        _item_to_response(i, accounts.get(i.account_id, ""), devices_map.get(i.assigned_device_id, ""))
        for i in items
    ]
    return resp


@router.patch("/{channel_id}")
async def update_channel(
    channel_id: str,
    request: ChannelUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    if not request.status:
        raise HTTPException(status_code=400, detail="需要提供 status 字段")
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    try:
        channel_service.update_channel_status(db, channel_id, request.status, user_id=scope_user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 通道恢复后广播 new_task_available，让在线设备立即领取
    if request.status == "active":
        await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})

    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"}, user_ids=resource_user_ids(db, Channel, channel_id))
    return {"status": "updated", "id": channel_id}


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    try:
        channel_service.soft_delete_channel(db, channel_id, user_id=scope_user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"}, user_ids=resource_user_ids(db, Channel, channel_id))
    return {"deleted": True, "id": channel_id}


@router.post("/{channel_id}/items")
async def append_items(
    channel_id: str,
    request: ChannelAppendItems,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    try:
        channel_service.append_items(db, channel_id, request.keywords, user_id=scope_user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"}, user_ids=resource_user_ids(db, Channel, channel_id))
    return {"appended": len(request.keywords), "channel_id": channel_id}


@router.patch("/{channel_id}/items/{item_id}")
async def update_item(
    channel_id: str,
    item_id: str,
    request: ChannelItemUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    if not request.status:
        raise HTTPException(status_code=400, detail="需要提供 status 字段")
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    try:
        channel_service.update_item_status(db, item_id, request.status, user_id=scope_user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"}, user_ids=_item_owner_ids(db, [item_id], user))
    return {"status": "updated", "item_id": item_id}


# ── Channel edit endpoints ──
# NOTE: /items/* routes must be registered before /{channel_id} to avoid
# "items" being captured as a channel_id parameter.


@router.put("/items/batch")
async def batch_edit_items(
    request: BatchEditRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    result = channel_service.batch_edit_items(
        db,
        request.item_ids,
        account_id=request.account_id,
        assigned_device_id=request.assigned_device_id,
        user_id=scope_user_id,
    )
    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"}, user_ids=_item_owner_ids(db, request.item_ids, user))
    return result


@router.put("/items/{item_id}")
async def edit_channel_item(
    item_id: str,
    request: ChannelItemEditRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    try:
        item = channel_service.edit_item(
            db,
            item_id,
            account_id=request.account_id,
            assigned_device_id=request.assigned_device_id,
            keyword=request.keyword,
            user_id=scope_user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"}, user_ids=_item_owner_ids(db, [item_id], user))

    account_nickname = ""
    device_name = ""
    if item.account_id:
        acc = db.query(Account).filter(Account.id == item.account_id).first()
        account_nickname = acc.nickname if acc else ""
    if item.assigned_device_id:
        dev = db.query(Device).filter(Device.id == item.assigned_device_id).first()
        device_name = dev.name if dev else ""

    return _item_to_response(item, account_nickname, device_name)


@router.put("/{channel_id}")
async def edit_channel(
    channel_id: str,
    request: ChannelEditRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    try:
        ch = channel_service.edit_channel(
            db,
            channel_id,
            group_id=request.group_id,
            account_mode=request.account_mode,
            account_id=request.account_id,
            params_template=request.params_template,
            cooldown_seconds=request.cooldown_seconds,
            sync_to_items=request.sync_to_items,
            user_id=scope_user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await pair_ws_manager.broadcast_to_admins({"event": "channels_changed"}, user_ids=resource_user_ids(db, Channel, channel_id))
    await pair_ws_manager.broadcast_to_devices({"event": "new_task_available"})
    group = db.query(AccountGroup).filter(AccountGroup.id == ch.group_id).first()
    stats = channel_service.get_channel_stats(db, ch.id)
    return _channel_to_response(ch, stats, group.name if group else "")
