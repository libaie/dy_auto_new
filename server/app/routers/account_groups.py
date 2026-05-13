"""Account groups CRUD API."""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.db_models import AccountGroup, AccountGroupMember, Account
from app.deps import verify_admin_token
from app.models import AccountGroupCreate, AccountGroupUpdate, AccountGroupMemberRequest
from app.ws_manager import pair_ws_manager

router = APIRouter(prefix="/api/account-groups", tags=["account-groups"])


def _group_to_dict(group: AccountGroup, member_count: int = 0) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description or "",
        "member_count": member_count,
        "created_at": str(group.created_at) if group.created_at else None,
        "updated_at": str(group.updated_at) if group.updated_at else None,
    }


@router.post("")
async def create_group(
    request: AccountGroupCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    existing = db.query(AccountGroup).filter(AccountGroup.name == request.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="分组名称已存在")
    group = AccountGroup(name=request.name, description=request.description)
    db.add(group)
    db.commit()
    db.refresh(group)
    await pair_ws_manager.broadcast_to_admins({"event": "account_groups_changed"})
    return _group_to_dict(group, 0)


@router.get("")
def list_groups(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    member_counts = (
        db.query(
            AccountGroupMember.group_id,
            func.count(AccountGroupMember.id).label("cnt"),
        )
        .group_by(AccountGroupMember.group_id)
        .subquery()
    )
    query = (
        db.query(AccountGroup, func.coalesce(member_counts.c.cnt, 0).label("member_count"))
        .outerjoin(member_counts, AccountGroup.id == member_counts.c.group_id)
        .order_by(AccountGroup.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    results = query.all()
    total = db.query(AccountGroup).count()
    return {
        "groups": [_group_to_dict(g, mc) for g, mc in results],
        "total": total,
    }


@router.get("/{group_id}")
def get_group(
    group_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    member_count = db.query(AccountGroupMember).filter(AccountGroupMember.group_id == group_id).count()
    return _group_to_dict(group, member_count)


@router.put("/{group_id}")
async def update_group(
    group_id: str,
    request: AccountGroupUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    if request.name is not None:
        dup = db.query(AccountGroup).filter(AccountGroup.name == request.name, AccountGroup.id != group_id).first()
        if dup:
            raise HTTPException(status_code=409, detail="分组名称已存在")
        group.name = request.name
    if request.description is not None:
        group.description = request.description
    db.commit()
    db.refresh(group)
    member_count = db.query(AccountGroupMember).filter(AccountGroupMember.group_id == group_id).count()
    await pair_ws_manager.broadcast_to_admins({"event": "account_groups_changed"})
    return _group_to_dict(group, member_count)


@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    db.delete(group)
    db.commit()
    await pair_ws_manager.broadcast_to_admins({"event": "account_groups_changed"})
    return {"deleted": True, "id": group_id}


@router.get("/{group_id}/members")
def list_members(
    group_id: str,
    status: str = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    query = (
        db.query(Account)
        .join(AccountGroupMember, AccountGroupMember.account_id == Account.id)
        .filter(AccountGroupMember.group_id == group_id)
    )
    if status:
        query = query.filter(Account.status == status)
    accounts = query.order_by(Account.created_at.desc()).all()
    return {
        "members": [
            {
                "id": a.id,
                "nickname": a.nickname,
                "douyin_id": a.douyin_id,
                "status": a.status,
            }
            for a in accounts
        ],
        "total": len(accounts),
    }


@router.post("/{group_id}/members")
async def add_members(
    group_id: str,
    request: AccountGroupMemberRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    # Validate all account_ids exist before adding
    existing_accounts = {
        a.id for a in db.query(Account.id).filter(Account.id.in_(request.account_ids)).all()
    }
    invalid_ids = [aid for aid in request.account_ids if aid not in existing_accounts]
    if invalid_ids:
        raise HTTPException(status_code=400, detail=f"以下账号不存在: {', '.join(invalid_ids)}")
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
    await pair_ws_manager.broadcast_to_admins({"event": "account_groups_changed"})
    return {"added": added, "count": len(added)}


@router.delete("/{group_id}/members")
async def remove_members(
    group_id: str,
    request: AccountGroupMemberRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    count = (
        db.query(AccountGroupMember)
        .filter(
            AccountGroupMember.group_id == group_id,
            AccountGroupMember.account_id.in_(request.account_ids),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    await pair_ws_manager.broadcast_to_admins({"event": "account_groups_changed"})
    return {"removed": count}
