"""Account groups CRUD API."""
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
    return group_use_cases.list_groups(db, skip, limit, user)


@router.get("/{group_id}")
def get_group(
    group_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
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
    try:
        result = group_use_cases.remove_members(db, group_id, request, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="分组不存在")
    await realtime_events.broadcast_account_groups_changed()
    return result
