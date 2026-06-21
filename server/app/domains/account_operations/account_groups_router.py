"""账号运营业务域模块。

账号运营业务域，负责账号、分组、频道、链路和账号侧读写用例。本文件负责 account_groups_router 相关业务规则、状态转换和外部系统边界。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role, verify_admin_token
from app.models import AccountGroupCreate, AccountGroupMemberRequest, AccountGroupUpdate

from . import group_use_cases, realtime_events

router = APIRouter(prefix="/api/account-groups", tags=["account-groups"])


@router.post("")
async def create_group(
    request: AccountGroupCreate,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    """业务函数：处理 create_group 对应的业务流程、校验或数据转换。"""
    user_id, _ = user
    try:
        group = group_use_cases.create_group(db, request, user_id)
    except group_use_cases.DuplicateNameError as error:
        raise HTTPException(status_code=409, detail=str(error))
    await realtime_events.broadcast_account_groups_changed()
    return group


@router.get("")
def list_groups(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 list_groups 对应的业务流程、校验或数据转换。"""
    return group_use_cases.list_groups(db, skip, limit, user)


@router.get("/{group_id}")
def get_group(
    group_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 get_group 对应的业务流程、校验或数据转换。"""
    try:
        return group_use_cases.get_group(db, group_id, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="分组不存在")


@router.put("/{group_id}")
async def update_group(
    group_id: str,
    request: AccountGroupUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 update_group 对应的业务流程、校验或数据转换。"""
    try:
        group = group_use_cases.update_group(db, group_id, request, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="分组不存在")
    except group_use_cases.DuplicateNameError as error:
        raise HTTPException(status_code=409, detail=str(error))
    await realtime_events.broadcast_account_groups_changed()
    return group


@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 delete_group 对应的业务流程、校验或数据转换。"""
    try:
        result = group_use_cases.delete_group(db, group_id, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="分组不存在")
    await realtime_events.broadcast_account_groups_changed()
    return result


@router.get("/{group_id}/members")
def list_members(
    group_id: str,
    status: str = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 list_members 对应的业务流程、校验或数据转换。"""
    try:
        return group_use_cases.list_members(db, group_id, status, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="分组不存在")


@router.post("/{group_id}/members")
async def add_members(
    group_id: str,
    request: AccountGroupMemberRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 add_members 对应的业务流程、校验或数据转换。"""
    try:
        result = group_use_cases.add_members(db, group_id, request, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="分组不存在")
    except group_use_cases.InvalidAccountIdsError as error:
        raise HTTPException(status_code=400, detail=str(error))
    await realtime_events.broadcast_account_groups_changed()
    return result


@router.delete("/{group_id}/members")
async def remove_members(
    group_id: str,
    request: AccountGroupMemberRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 remove_members 对应的业务流程、校验或数据转换。"""
    try:
        result = group_use_cases.remove_members(db, group_id, request, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="分组不存在")
    await realtime_events.broadcast_account_groups_changed()
    return result
