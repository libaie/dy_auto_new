"""Account CRUD use cases."""

from app.config import bj_now
from app.db_models import Account, Device, Task as DBTask

from .read_models import account_to_dict


def create_account(db, request, user_id: str) -> dict:
    account = Account(
        nickname=request.nickname,
        douyin_id=request.douyin_id,
        group=request.group,
        status=request.status,
        daily_limits=request.daily_limits,
        user_id=user_id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account_to_dict(account)


def list_accounts(db, skip: int, limit: int, include_deleted: bool, user: tuple) -> dict:
    limit = min(limit, 100)
    user_id, role = user
    query = db.query(Account)
    if not include_deleted:
        query = query.filter(Account.status != "deleted")
    if role != "admin":
        query = query.filter(Account.user_id == user_id)
    total = query.count()
    accounts = query.order_by(Account.created_at.desc()).offset(skip).limit(limit).all()
    return {"accounts": [account_to_dict(account) for account in accounts], "total": total}


def get_account(db, account_id: str, include_deleted: bool, user: tuple) -> dict:
    account = _account_query(db, account_id, include_deleted, user).first()
    if not account:
        raise LookupError("Account not found")
    return account_to_dict(account)


def update_account(db, account_id: str, request, user: tuple) -> dict:
    account = _account_query(db, account_id, include_deleted=True, user=user).first()
    if not account:
        raise LookupError("Account not found")

    if request.nickname is not None:
        account.nickname = request.nickname
    if request.douyin_id is not None:
        account.douyin_id = request.douyin_id
    if request.group is not None:
        account.group = request.group
    if request.status is not None:
        account.status = request.status
    if request.daily_limits is not None:
        account.daily_limits = request.daily_limits
    if request.cookie is not None:
        account.cookie = request.cookie

    db.commit()
    db.refresh(account)
    return account_to_dict(account)


def delete_account(db, account_id: str, user: tuple) -> dict:
    account = _account_query(db, account_id, include_deleted=True, user=user).first()
    if not account:
        raise LookupError("Account not found")

    db.query(Device).filter(Device.bound_account_id == account_id).update(
        {"bound_account_id": None}, synchronize_session=False
    )
    db.query(DBTask).filter(
        DBTask.account_id == account_id,
        DBTask.status.in_(["pending", "running"]),
    ).update(
        {"status": "cancelled", "result": {"error": "account deleted"}, "completed_at": bj_now()},
        synchronize_session=False,
    )
    account.status = "deleted"

    db.commit()
    return {"deleted": True, "id": account_id}


def _account_query(db, account_id: str, include_deleted: bool, user: tuple):
    user_id, role = user
    query = db.query(Account).filter(Account.id == account_id)
    if not include_deleted:
        query = query.filter(Account.status != "deleted")
    if role != "admin":
        query = query.filter(Account.user_id == user_id)
    return query
