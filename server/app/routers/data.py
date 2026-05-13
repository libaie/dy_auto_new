"""Data center admin API — collected comments, users, conversations."""
from fastapi import APIRouter, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import CollectedComment, CollectedUser, Conversation, Device

router = APIRouter(prefix="/api/data", tags=["data"])


def _paginate(query, skip: int, limit: int) -> dict:
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return {"items": items, "total": total}


@router.get("/comments")
def list_comments(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(CollectedComment)
    if keyword:
        query = query.filter(CollectedComment.keyword == keyword)
    if account_id:
        device_ids = db.query(Device.id).filter(Device.bound_account_id == account_id).subquery()
        query = query.filter(CollectedComment.device_id.in_(device_ids))
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            CollectedComment.nickname.like(pattern),
            CollectedComment.content.like(pattern),
        ))
    if task_id:
        query = query.filter(CollectedComment.task_id == task_id)
    query = query.order_by(CollectedComment.created_at.desc())
    return _paginate(query, skip, limit)


@router.get("/users")
def list_users(
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(CollectedUser)
    if account_id:
        device_ids = db.query(Device.id).filter(Device.bound_account_id == account_id).subquery()
        query = query.filter(CollectedUser.device_id.in_(device_ids))
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            CollectedUser.nickname.like(pattern),
            CollectedUser.douyin_id.like(pattern),
        ))
    if task_id:
        query = query.filter(CollectedUser.task_id == task_id)
    query = query.order_by(CollectedUser.created_at.desc())
    return _paginate(query, skip, limit)


@router.get("/conversations")
def list_conversations(
    account_id: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(Conversation)
    if account_id:
        query = query.filter(Conversation.account_id == account_id)
    if stage:
        query = query.filter(Conversation.current_stage == stage)
    if status:
        query = query.filter(Conversation.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            Conversation.recipient_nickname.like(pattern),
            Conversation.last_dm_content.like(pattern),
            Conversation.recipient_douyin_id.like(pattern),
        ))
    if task_id:
        query = query.filter(Conversation.task_id == task_id)
    query = query.order_by(Conversation.updated_at.desc())
    return _paginate(query, skip, limit)
