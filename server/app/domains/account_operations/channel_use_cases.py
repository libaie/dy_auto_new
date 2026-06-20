"""Channel CRUD and item mutation use cases."""

from app.db.models.account_operations import Account, AccountGroup
from app.db_models import ChannelItem, Device

from .adapters import channel_service
from .read_models import channel_item_to_response, channel_to_response


def create_channel(db, request, user_id: str) -> dict:
    channel = channel_service.create_channel(
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
    group = db.query(AccountGroup).filter(AccountGroup.id == channel.group_id).first()
    stats = channel_service.get_channel_stats(db, channel.id)
    return channel_to_response(channel, stats, group.name if group else "")


def list_channels(db, user: tuple) -> dict:
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    channels = channel_service.list_channels(db, user_id=scope_user_id)
    group_ids = list({channel.group_id for channel in channels})
    groups = {
        group.id: group.name
        for group in db.query(AccountGroup).filter(AccountGroup.id.in_(group_ids)).all()
    } if group_ids else {}

    channel_ids = [channel.id for channel in channels]
    stats_map = channel_service.get_channels_stats_batch(db, channel_ids)

    result = []
    for channel in channels:
        stats = stats_map.get(channel.id, {
            "total": 0,
            "pending": 0,
            "assigned": 0,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
        })
        result.append(channel_to_response(channel, stats, groups.get(channel.group_id, "")))
    return {"channels": result, "total": len(result)}


def get_channel(db, channel_id: str, user: tuple) -> dict:
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    channel = channel_service.get_channel(db, channel_id, user_id=scope_user_id)
    if not channel:
        raise LookupError("通道不存在")

    group = db.query(AccountGroup).filter(AccountGroup.id == channel.group_id).first()
    stats = channel_service.get_channel_stats(db, channel.id)
    response = channel_to_response(channel, stats, group.name if group else "")

    items = db.query(ChannelItem).filter(ChannelItem.channel_id == channel_id).order_by(ChannelItem.queue_position).all()
    account_ids = list({item.account_id for item in items})
    device_ids = list({item.assigned_device_id for item in items if item.assigned_device_id})
    accounts = {account.id: account.nickname for account in db.query(Account).filter(Account.id.in_(account_ids)).all()} if account_ids else {}
    devices = {device.id: device.name for device in db.query(Device).filter(Device.id.in_(device_ids)).all()} if device_ids else {}

    response["items"] = [
        channel_item_to_response(item, accounts.get(item.account_id, ""), devices.get(item.assigned_device_id, ""))
        for item in items
    ]
    return response


def update_channel_status(db, channel_id: str, status: str, user: tuple) -> dict:
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    channel_service.update_channel_status(db, channel_id, status, user_id=scope_user_id)
    return {"status": "updated", "id": channel_id}


def delete_channel(db, channel_id: str, user: tuple) -> dict:
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    channel_service.soft_delete_channel(db, channel_id, user_id=scope_user_id)
    return {"deleted": True, "id": channel_id}


def append_items(db, channel_id: str, keywords: list[str], user: tuple) -> dict:
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    channel_service.append_items(db, channel_id, keywords, user_id=scope_user_id)
    return {"appended": len(keywords), "channel_id": channel_id}


def update_item_status(db, item_id: str, status: str, user: tuple) -> dict:
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    channel_service.update_item_status(db, item_id, status, user_id=scope_user_id)
    return {"status": "updated", "item_id": item_id}


def batch_edit_items(db, request, user: tuple) -> dict:
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    return channel_service.batch_edit_items(
        db,
        request.item_ids,
        account_id=request.account_id,
        assigned_device_id=request.assigned_device_id,
        user_id=scope_user_id,
    )


def edit_channel_item(db, item_id: str, request, user: tuple) -> dict:
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    item = channel_service.edit_item(
        db,
        item_id,
        account_id=request.account_id,
        assigned_device_id=request.assigned_device_id,
        keyword=request.keyword,
        user_id=scope_user_id,
    )
    account_nickname = ""
    device_name = ""
    if item.account_id:
        account = db.query(Account).filter(Account.id == item.account_id).first()
        account_nickname = account.nickname if account else ""
    if item.assigned_device_id:
        device = db.query(Device).filter(Device.id == item.assigned_device_id).first()
        device_name = device.name if device else ""
    return channel_item_to_response(item, account_nickname, device_name)


def edit_channel(db, channel_id: str, request, user: tuple) -> dict:
    user_id, role = user
    scope_user_id = None if role == "admin" else user_id
    channel = channel_service.edit_channel(
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
    group = db.query(AccountGroup).filter(AccountGroup.id == channel.group_id).first()
    stats = channel_service.get_channel_stats(db, channel.id)
    return channel_to_response(channel, stats, group.name if group else "")
