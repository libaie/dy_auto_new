"""账号运营业务域模块。

账号运营业务域，负责账号、分组、频道、链路和账号侧读写用例。本文件负责 group_use_cases 相关业务规则、状态转换和外部系统边界。
"""

from sqlalchemy import func

from app.db.models.account_operations import Account, AccountGroup, AccountGroupMember

from .read_models import group_to_dict, member_to_dict


class DuplicateNameError(ValueError):
    """业务类：承载 DuplicateNameError 相关的数据结构、状态或业务协作。

    类参数：无显式类参数 承载该类的业务配置、状态或数据字段。
    """
    pass


class InvalidAccountIdsError(ValueError):
    """业务类：承载 InvalidAccountIdsError 相关的数据结构、状态或业务协作。

    类参数：无显式类参数 承载该类的业务配置、状态或数据字段。
    """
    pass


def create_group(db, request, user_id: str) -> dict:
    """业务函数：处理 create_group 对应的业务流程、校验或数据转换。

    入参：db、request、user_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    existing = db.query(AccountGroup).filter(AccountGroup.name == request.name, AccountGroup.user_id == user_id).first()
    if existing:
        raise DuplicateNameError("分组名称已存在")
    group = AccountGroup(name=request.name, description=request.description, user_id=user_id)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group_to_dict(group, 0)


def list_groups(db, skip: int, limit: int, user: tuple) -> dict:
    """业务函数：处理 list_groups 对应的业务流程、校验或数据转换。

    入参：db、skip、limit、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    limit = min(limit, 100)
    user_id, role = user
    member_counts = (
        db.query(
            AccountGroupMember.group_id,
            func.count(AccountGroupMember.id).label("cnt"),
        )
        .group_by(AccountGroupMember.group_id)
        .subquery()
    )
    base = db.query(AccountGroup)
    if role != "admin":
        base = base.filter(AccountGroup.user_id == user_id)
    query = (
        base.outerjoin(member_counts, AccountGroup.id == member_counts.c.group_id)
        .add_columns(func.coalesce(member_counts.c.cnt, 0).label("member_count"))
        .order_by(AccountGroup.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    results = query.all()
    total = base.count()
    return {
        "groups": [group_to_dict(group, member_count) for group, member_count in results],
        "total": total,
    }


def get_group(db, group_id: str, user: tuple) -> dict:
    """业务函数：处理 get_group 对应的业务流程、校验或数据转换。

    入参：db、group_id、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    group = _group_query(db, group_id, user).first()
    if not group:
        raise LookupError("分组不存在")
    member_count = db.query(AccountGroupMember).filter(AccountGroupMember.group_id == group_id).count()
    return group_to_dict(group, member_count)


def update_group(db, group_id: str, request, user: tuple) -> dict:
    """业务函数：处理 update_group 对应的业务流程、校验或数据转换。

    入参：db、group_id、request、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    group = _group_query(db, group_id, user).first()
    if not group:
        raise LookupError("分组不存在")
    if request.name is not None:
        duplicate = db.query(AccountGroup).filter(
            AccountGroup.name == request.name,
            AccountGroup.id != group_id,
            AccountGroup.user_id == group.user_id,
        ).first()
        if duplicate:
            raise DuplicateNameError("分组名称已存在")
        group.name = request.name
    if request.description is not None:
        group.description = request.description
    db.commit()
    db.refresh(group)
    member_count = db.query(AccountGroupMember).filter(AccountGroupMember.group_id == group_id).count()
    return group_to_dict(group, member_count)


def delete_group(db, group_id: str, user: tuple) -> dict:
    """业务函数：处理 delete_group 对应的业务流程、校验或数据转换。

    入参：db、group_id、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    group = _group_query(db, group_id, user).first()
    if not group:
        raise LookupError("分组不存在")
    db.delete(group)
    db.commit()
    return {"deleted": True, "id": group_id}


def list_members(db, group_id: str, status: str, user: tuple) -> dict:
    """业务函数：处理 list_members 对应的业务流程、校验或数据转换。

    入参：db、group_id、status、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    _require_group(db, group_id, user)
    user_id, role = user
    query = (
        db.query(Account)
        .join(AccountGroupMember, AccountGroupMember.account_id == Account.id)
        .filter(AccountGroupMember.group_id == group_id)
    )
    if role != "admin":
        query = query.filter(Account.user_id == user_id)
    if status:
        query = query.filter(Account.status == status)
    accounts = query.order_by(Account.created_at.desc()).all()
    return {
        "members": [member_to_dict(account) for account in accounts],
        "total": len(accounts),
    }


def add_members(db, group_id: str, request, user: tuple) -> dict:
    """业务函数：处理 add_members 对应的业务流程、校验或数据转换。

    入参：db、group_id、request、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    _require_group(db, group_id, user)
    user_id, role = user
    account_query = db.query(Account.id).filter(Account.id.in_(request.account_ids))
    if role != "admin":
        account_query = account_query.filter(Account.user_id == user_id)
    existing_accounts = {account.id for account in account_query.all()}
    invalid_ids = [account_id for account_id in request.account_ids if account_id not in existing_accounts]
    if invalid_ids:
        raise InvalidAccountIdsError(f"以下账号不存在: {', '.join(invalid_ids)}")

    added = []
    for account_id in request.account_ids:
        exists = db.query(AccountGroupMember).filter(
            AccountGroupMember.group_id == group_id,
            AccountGroupMember.account_id == account_id,
        ).first()
        if not exists:
            db.add(AccountGroupMember(group_id=group_id, account_id=account_id))
            added.append(account_id)
    db.commit()
    return {"added": added, "count": len(added)}


def remove_members(db, group_id: str, request, user: tuple) -> dict:
    """业务函数：处理 remove_members 对应的业务流程、校验或数据转换。

    入参：db、group_id、request、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    _require_group(db, group_id, user)
    count = (
        db.query(AccountGroupMember)
        .filter(
            AccountGroupMember.group_id == group_id,
            AccountGroupMember.account_id.in_(request.account_ids),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"removed": count}


def _group_query(db, group_id: str, user: tuple):
    """业务函数：处理 _group_query 对应的业务流程、校验或数据转换。

    入参：db、group_id、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    user_id, role = user
    query = db.query(AccountGroup).filter(AccountGroup.id == group_id)
    if role != "admin":
        query = query.filter(AccountGroup.user_id == user_id)
    return query


def _require_group(db, group_id: str, user: tuple):
    """业务函数：处理 _require_group 对应的业务流程、校验或数据转换。

    入参：db、group_id、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    group = _group_query(db, group_id, user).first()
    if not group:
        raise LookupError("分组不存在")
    return group
