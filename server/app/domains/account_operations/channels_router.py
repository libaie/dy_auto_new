"""账号运营业务域模块。

账号运营业务域，负责账号、分组、频道、链路和账号侧读写用例。本文件负责 channels_router 相关业务规则、状态转换和外部系统边界。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role, verify_admin_token
from app.models import (
    BatchEditRequest,
    ChannelAppendItems,
    ChannelCreate,
    ChannelEditRequest,
    ChannelItemEditRequest,
    ChannelItemUpdate,
    ChannelUpdate,
)

from . import channel_use_cases, realtime_events

router = APIRouter(prefix="/api/channels", tags=["channels"])


@router.post("")
async def create_channel(
    request: ChannelCreate,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    """业务函数：处理 create_channel 对应的业务流程、校验或数据转换。

    入参：request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    user_id, _ = user
    try:
        channel = channel_use_cases.create_channel(db, request, user_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    await realtime_events.broadcast_channels_changed()
    return channel


@router.get("")
def list_channels(
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 list_channels 对应的业务流程、校验或数据转换。

    入参：db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return channel_use_cases.list_channels(db, user)


@router.get("/{channel_id}")
def get_channel(
    channel_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 get_channel 对应的业务流程、校验或数据转换。

    入参：channel_id、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        return channel_use_cases.get_channel(db, channel_id, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="通道不存在")


@router.patch("/{channel_id}")
async def update_channel(
    channel_id: str,
    request: ChannelUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 update_channel 对应的业务流程、校验或数据转换。

    入参：channel_id、request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not request.status:
        raise HTTPException(status_code=400, detail="需要提供 status 字段")
    try:
        result = channel_use_cases.update_channel_status(db, channel_id, request.status, user)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if request.status == "active":
        await realtime_events.broadcast_new_task_available()

    await realtime_events.broadcast_channels_changed()
    return result


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 delete_channel 对应的业务流程、校验或数据转换。

    入参：channel_id、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        result = channel_use_cases.delete_channel(db, channel_id, user)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    await realtime_events.broadcast_channels_changed()
    return result


@router.post("/{channel_id}/items")
async def append_items(
    channel_id: str,
    request: ChannelAppendItems,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 append_items 对应的业务流程、校验或数据转换。

    入参：channel_id、request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        result = channel_use_cases.append_items(db, channel_id, request.keywords, user)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    await realtime_events.broadcast_channels_changed()
    return result


@router.patch("/{channel_id}/items/{item_id}")
async def update_item(
    channel_id: str,
    item_id: str,
    request: ChannelItemUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 update_item 对应的业务流程、校验或数据转换。

    入参：channel_id、item_id、request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not request.status:
        raise HTTPException(status_code=400, detail="需要提供 status 字段")
    try:
        result = channel_use_cases.update_item_status(db, item_id, request.status, user)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    await realtime_events.broadcast_channels_changed()
    return result


# /items/* routes must be registered before /{channel_id}.


@router.put("/items/batch")
async def batch_edit_items(
    request: BatchEditRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 batch_edit_items 对应的业务流程、校验或数据转换。

    入参：request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    result = channel_use_cases.batch_edit_items(db, request, user)
    await realtime_events.broadcast_channels_changed()
    return result


@router.put("/items/{item_id}")
async def edit_channel_item(
    item_id: str,
    request: ChannelItemEditRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 edit_channel_item 对应的业务流程、校验或数据转换。

    入参：item_id、request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        item = channel_use_cases.edit_channel_item(db, item_id, request, user)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    await realtime_events.broadcast_channels_changed()
    return item


@router.put("/{channel_id}")
async def edit_channel(
    channel_id: str,
    request: ChannelEditRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 edit_channel 对应的业务流程、校验或数据转换。

    入参：channel_id、request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        channel = channel_use_cases.edit_channel(db, channel_id, request, user)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    await realtime_events.broadcast_channels_changed()
    await realtime_events.broadcast_new_task_available()
    return channel
