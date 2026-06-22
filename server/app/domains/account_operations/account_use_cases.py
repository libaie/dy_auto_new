"""账号运营业务域模块。

账号运营业务域，负责账号、分组、频道、链路和账号侧读写用例。本文件负责 account_use_cases 相关业务规则、状态转换和外部系统边界。
"""

from app.config import bj_now
from app.db.models.account_operations import Account
from app.db.models import Device, Task as DBTask

from .read_models import account_to_dict


def create_account(db, request, user_id: str) -> dict:
    """业务函数：处理 create_account 对应的业务流程、校验或数据转换。

    入参：db、request、user_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 list_accounts 对应的业务流程、校验或数据转换。

    入参：db、skip、limit、include_deleted、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 get_account 对应的业务流程、校验或数据转换。

    入参：db、account_id、include_deleted、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    account = _account_query(db, account_id, include_deleted, user).first()
    if not account:
        raise LookupError("Account not found")
    return account_to_dict(account)


def update_account(db, account_id: str, request, user: tuple) -> dict:
    """业务函数：处理 update_account 对应的业务流程、校验或数据转换。

    入参：db、account_id、request、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 delete_account 对应的业务流程、校验或数据转换。

    入参：db、account_id、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 _account_query 对应的业务流程、校验或数据转换。

    入参：db、account_id、include_deleted、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    user_id, role = user
    query = db.query(Account).filter(Account.id == account_id)
    if not include_deleted:
        query = query.filter(Account.status != "deleted")
    if role != "admin":
        query = query.filter(Account.user_id == user_id)
    return query
