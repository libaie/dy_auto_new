"""Account management CRUD API."""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import Account
from app.deps import verify_admin_token

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountCreateRequest(BaseModel):
    nickname: str
    douyin_id: str = ""
    group: str = "default"
    status: str = "active"
    daily_limits: Optional[dict[str, int]] = None


class AccountUpdateRequest(BaseModel):
    nickname: Optional[str] = None
    douyin_id: Optional[str] = None
    group: Optional[str] = None
    status: Optional[str] = None
    daily_limits: Optional[dict[str, int]] = None
    cookie: Optional[str] = None


def _account_to_dict(acc: Account) -> dict:
    return {
        "id": acc.id,
        "nickname": acc.nickname,
        "douyin_id": acc.douyin_id,
        "group": acc.group,
        "status": acc.status,
        "daily_limits": acc.daily_limits,
        "created_at": str(acc.created_at) if acc.created_at else None,
        "updated_at": str(acc.updated_at) if acc.updated_at else None,
    }


@router.post("")
def create_account(
    request: AccountCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    acc = Account(
        nickname=request.nickname,
        douyin_id=request.douyin_id,
        group=request.group,
        status=request.status,
        daily_limits=request.daily_limits,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return _account_to_dict(acc)


@router.get("")
def list_accounts(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    total = db.query(Account).count()
    accounts = db.query(Account).order_by(Account.created_at.desc()).offset(skip).limit(limit).all()
    return {"accounts": [_account_to_dict(a) for a in accounts], "total": total}


@router.get("/{account_id}")
def get_account(
    account_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    return _account_to_dict(acc)


@router.put("/{account_id}")
def update_account(
    account_id: str,
    request: AccountUpdateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")

    if request.nickname is not None:
        acc.nickname = request.nickname
    if request.douyin_id is not None:
        acc.douyin_id = request.douyin_id
    if request.group is not None:
        acc.group = request.group
    if request.status is not None:
        acc.status = request.status
    if request.daily_limits is not None:
        acc.daily_limits = request.daily_limits
    if request.cookie is not None:
        acc.cookie = request.cookie

    db.commit()
    db.refresh(acc)
    return _account_to_dict(acc)


@router.delete("/{account_id}")
def delete_account(
    account_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")

    from app.db_models import Device, Task as DBTask
    # 1. 解绑关联设备
    db.query(Device).filter(Device.bound_account_id == account_id).update(
        {"bound_account_id": None}, synchronize_session=False
    )
    # 2. 取消该账号的 pending/running 任务
    db.query(DBTask).filter(
        DBTask.account_id == account_id,
        DBTask.status.in_(["pending", "running"]),
    ).update({"status": "failed", "result": '{"error": "account deleted"}'}, synchronize_session=False)

    db.delete(acc)
    db.commit()
    return {"deleted": True, "id": account_id}
