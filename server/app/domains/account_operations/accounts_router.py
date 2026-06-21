"""账号运营业务域模块。

账号运营业务域，负责账号、分组、频道、链路和账号侧读写用例。本文件负责 accounts_router 相关业务规则、状态转换和外部系统边界。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role, verify_admin_token

from . import account_use_cases, realtime_events

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountCreateRequest(BaseModel):
    """业务类：承载 AccountCreateRequest 相关的数据结构、状态或业务协作。"""
    nickname: str
    douyin_id: str = ""
    group: str = "default"
    status: str = "active"
    daily_limits: Optional[dict[str, int]] = None


class AccountUpdateRequest(BaseModel):
    """业务类：承载 AccountUpdateRequest 相关的数据结构、状态或业务协作。"""
    nickname: Optional[str] = None
    douyin_id: Optional[str] = None
    group: Optional[str] = None
    status: Optional[str] = None
    daily_limits: Optional[dict[str, int]] = None
    cookie: Optional[str] = None


@router.post("")
async def create_account(
    request: AccountCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    """业务函数：处理 create_account 对应的业务流程、校验或数据转换。"""
    user_id, _ = user
    account = account_use_cases.create_account(db, request, user_id)
    await realtime_events.broadcast_accounts_changed()
    return account


@router.get("")
def list_accounts(
    skip: int = 0,
    limit: int = 50,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 list_accounts 对应的业务流程、校验或数据转换。"""
    return account_use_cases.list_accounts(db, skip, limit, include_deleted, user)


@router.get("/{account_id}")
def get_account(
    account_id: str,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 get_account 对应的业务流程、校验或数据转换。"""
    try:
        return account_use_cases.get_account(db, account_id, include_deleted, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="Account not found")


@router.put("/{account_id}")
async def update_account(
    account_id: str,
    request: AccountUpdateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 update_account 对应的业务流程、校验或数据转换。"""
    try:
        account = account_use_cases.update_account(db, account_id, request, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="Account not found")
    await realtime_events.broadcast_accounts_changed()
    return account


@router.delete("/{account_id}")
async def delete_account(
    account_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 delete_account 对应的业务流程、校验或数据转换。"""
    try:
        result = account_use_cases.delete_account(db, account_id, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="Account not found")
    await realtime_events.broadcast_accounts_changed()
    return result
