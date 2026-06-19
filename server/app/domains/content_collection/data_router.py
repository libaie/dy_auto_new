"""Data center admin API — collected comments, users, conversations."""
import io
from fastapi import APIRouter, Query, Depends, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, cast, Integer, desc, asc, func
from openpyxl import Workbook

from app.database import get_db
from app.deps import verify_admin_token
from app.config import bj_now
from app.db_models import CollectedComment, CollectedUser, Conversation, Device, Task

router = APIRouter(prefix="/api/data", tags=["data"])


def _build_xlsx(headers: list[str], rows: list[list]) -> io.BytesIO:
    wb = Workbook(write_only=True)
    ws = wb.create_sheet()
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _stream_xlsx(filename: str, buf: io.BytesIO) -> StreamingResponse:
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _paginate(query, skip: int, limit: int) -> dict:
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return {"items": items, "total": total}


def _apply_user_sort(query, sort_by: Optional[str], sort_order: Optional[str]):
    numeric_sort_fields = {
        "fans_count": func.coalesce(cast(CollectedUser.fans_count, Integer), 0),
        "likes_count": func.coalesce(cast(CollectedUser.likes_count, Integer), 0),
        "follow_count": func.coalesce(cast(CollectedUser.follow_count, Integer), 0),
        "works_count": func.coalesce(cast(CollectedUser.works_count, Integer), 0),
        "created_at": CollectedUser.created_at,
    }
    order_col = numeric_sort_fields.get(sort_by, CollectedUser.created_at)
    order_fn = desc if sort_order == "desc" else asc
    return query.order_by(order_fn(order_col), CollectedUser.id.asc())


@router.get("/comments")
def list_comments(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(CollectedComment)
    if keyword:
        query = query.filter(CollectedComment.keyword == keyword)
    if account_id:
        device_ids = db.query(Device.id).filter(Device.bound_account_id == account_id).subquery()
        query = query.filter(CollectedComment.device_id.in_(device_ids))
    if search:
        query = query.filter(or_(
            _like_contains(CollectedComment.nickname, search),
            _like_contains(CollectedComment.content, search),
        ))
    if task_id:
        query = query.filter(CollectedComment.task_id == task_id)
    user_id, role = user
    if role != 'admin':
        query = query.join(Task, CollectedComment.task_id == Task.id).filter(Task.user_id == user_id)
    query = query.order_by(CollectedComment.created_at.desc(), CollectedComment.id.asc())
    return _paginate(query, skip, limit)


@router.get("/users")
def list_users(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    is_private: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("desc"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(CollectedUser)
    if keyword:
        query = query.filter(_like_contains(CollectedUser.keyword, keyword))
    if account_id:
        device_ids = db.query(Device.id).filter(Device.bound_account_id == account_id).subquery()
        query = query.filter(CollectedUser.device_id.in_(device_ids))
    if search:
        query = query.filter(or_(
            _like_contains(CollectedUser.nickname, search),
            _like_contains(CollectedUser.douyin_id, search),
            _like_contains(CollectedUser.ip_location, search),
            _like_contains(CollectedUser.source_comment_content, search),
        ))
    if task_id:
        query = query.filter(CollectedUser.task_id == task_id)
    user_id, role = user
    if role != 'admin':
        query = query.join(Task, CollectedUser.task_id == Task.id).filter(Task.user_id == user_id)
    if is_private == "yes":
        query = query.filter(CollectedUser.is_private == "是")
    elif is_private == "no":
        query = query.filter(or_(
            CollectedUser.is_private.is_(None),
            CollectedUser.is_private == "否",
        ))
    if date_from:
        try:
            d = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(CollectedUser.created_at >= d)
        except ValueError:
            pass
    if date_to:
        try:
            d = datetime.strptime(date_to, "%Y-%m-%d")
            d = d.replace(hour=23, minute=59, second=59)
            query = query.filter(CollectedUser.created_at <= d)
        except ValueError:
            pass

    query = _apply_user_sort(query, sort_by, sort_order)

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
    user = Depends(verify_admin_token),
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
        query = query.filter(or_(
            _like_contains(Conversation.recipient_nickname, search),
            _like_contains(Conversation.last_dm_content, search),
            _like_contains(Conversation.recipient_douyin_id, search),
        ))
    if task_id:
        query = query.filter(Conversation.task_id == task_id)
    user_id, role = user
    if role != 'admin':
        query = query.join(Task, Conversation.task_id == Task.id).filter(Task.user_id == user_id)
    query = query.order_by(Conversation.updated_at.desc(), Conversation.id.asc())
    return _paginate(query, skip, limit)


# === Export endpoints ===

MAX_EXPORT_ROWS = 50000


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards to prevent accidental full-table matches."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_like(pattern: str) -> str:
    return f"%{_escape_like(pattern)}%"


def _like_contains(column, value: str):
    return column.like(_build_like(value), escape="\\")


@router.get("/export/comments")
def export_comments(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    skip: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    query = db.query(CollectedComment)
    if keyword:
        query = query.filter(CollectedComment.keyword == keyword)
    if account_id:
        device_ids = db.query(Device.id).filter(Device.bound_account_id == account_id).subquery()
        query = query.filter(CollectedComment.device_id.in_(device_ids))
    if search:
        query = query.filter(or_(
            _like_contains(CollectedComment.nickname, search),
            _like_contains(CollectedComment.content, search),
        ))
    if task_id:
        query = query.filter(CollectedComment.task_id == task_id)
    if date_from:
        try:
            d = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(CollectedComment.created_at >= d)
        except ValueError:
            pass
    if date_to:
        try:
            d = datetime.strptime(date_to, "%Y-%m-%d")
            d = d.replace(hour=23, minute=59, second=59)
            query = query.filter(CollectedComment.created_at <= d)
        except ValueError:
            pass

    user_id, role = user
    if role != 'admin':
        query = query.join(Task, CollectedComment.task_id == Task.id).filter(Task.user_id == user_id)

    query = query.order_by(CollectedComment.created_at.desc(), CollectedComment.id.asc())
    is_paged = limit is not None
    if is_paged:
        if skip: query = query.offset(skip)
        query = query.limit(min(limit, 100))
    else:
        count = query.count()
        if count > MAX_EXPORT_ROWS:
            raise HTTPException(400, f"导出数据量 ({count} 条) 超过上限 ({MAX_EXPORT_ROWS} 条)，请缩小筛选范围")
    rows = query.all()

    headers = ["昵称", "内容", "AI回复", "关键词", "点赞数", "回复数", "IP属地", "意向省份", "意向城市", "意向景点", "是否作者", "评论时间", "采集时间"]
    data = [[
        r.nickname or "", r.content or "", r.ai_reply or "", r.keyword or "",
        r.like_count or "", r.reply_count or "", r.location or "",
        r.intended_province or "", r.intended_city or "", r.intended_attraction or "",
        "是" if r.is_author else "否", r.time_str or "", str(r.created_at or "")
    ] for r in rows]

    buf = _build_xlsx(headers, data)
    return _stream_xlsx(f"comments_{bj_now().strftime('%Y%m%d')}.xlsx", buf)


@router.get("/export/users")
def export_users(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    is_private: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("desc"),
    skip: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    query = db.query(CollectedUser)
    if keyword:
        query = query.filter(_like_contains(CollectedUser.keyword, keyword))
    if account_id:
        device_ids = db.query(Device.id).filter(Device.bound_account_id == account_id).subquery()
        query = query.filter(CollectedUser.device_id.in_(device_ids))
    if search:
        query = query.filter(or_(
            _like_contains(CollectedUser.nickname, search),
            _like_contains(CollectedUser.douyin_id, search),
            _like_contains(CollectedUser.ip_location, search),
            _like_contains(CollectedUser.source_comment_content, search),
        ))
    if task_id:
        query = query.filter(CollectedUser.task_id == task_id)
    if is_private == "yes":
        query = query.filter(CollectedUser.is_private == "是")
    elif is_private == "no":
        query = query.filter(or_(
            CollectedUser.is_private.is_(None),
            CollectedUser.is_private == "否",
        ))
    if date_from:
        try:
            d = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(CollectedUser.created_at >= d)
        except ValueError:
            pass
    if date_to:
        try:
            d = datetime.strptime(date_to, "%Y-%m-%d")
            d = d.replace(hour=23, minute=59, second=59)
            query = query.filter(CollectedUser.created_at <= d)
        except ValueError:
            pass

    user_id, role = user
    if role != 'admin':
        query = query.join(Task, CollectedUser.task_id == Task.id).filter(Task.user_id == user_id)

    query = _apply_user_sort(query, sort_by, sort_order)
    is_paged = limit is not None
    if is_paged:
        if skip: query = query.offset(skip)
        query = query.limit(min(limit, 100))
    else:
        count = query.count()
        if count > MAX_EXPORT_ROWS:
            raise HTTPException(400, f"导出数据量 ({count} 条) 超过上限 ({MAX_EXPORT_ROWS} 条)，请缩小筛选范围")
    rows = query.all()

    headers = ["昵称", "抖音号", "关键词", "入口评论", "意向省份", "意向城市", "意向景点", "获赞", "关注", "粉丝", "作品", "性别", "年龄", "IP属地", "私密账号", "采集时间"]
    data = [[
        r.nickname or "", r.douyin_id or "", r.keyword or "", r.source_comment_content or "",
        r.intended_province or "", r.intended_city or "", r.intended_attraction or "",
        r.likes_count or "", r.follow_count or "", r.fans_count or "", r.works_count or "",
        r.gender or "", r.age or "", r.ip_location or "", r.is_private or "",
        str(r.created_at or "")
    ] for r in rows]

    buf = _build_xlsx(headers, data)
    return _stream_xlsx(f"users_{bj_now().strftime('%Y%m%d')}.xlsx", buf)


@router.get("/export/conversations")
def export_conversations(
    account_id: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    skip: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    query = db.query(Conversation)
    if account_id:
        query = query.filter(Conversation.account_id == account_id)
    if stage:
        query = query.filter(Conversation.current_stage == stage)
    if status:
        query = query.filter(Conversation.status == status)
    if search:
        query = query.filter(or_(
            _like_contains(Conversation.recipient_nickname, search),
            _like_contains(Conversation.last_dm_content, search),
            _like_contains(Conversation.recipient_douyin_id, search),
        ))
    if task_id:
        query = query.filter(Conversation.task_id == task_id)
    if date_from:
        try:
            d = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(Conversation.created_at >= d)
        except ValueError:
            pass
    if date_to:
        try:
            d = datetime.strptime(date_to, "%Y-%m-%d")
            d = d.replace(hour=23, minute=59, second=59)
            query = query.filter(Conversation.created_at <= d)
        except ValueError:
            pass

    user_id, role = user
    if role != 'admin':
        query = query.join(Task, Conversation.task_id == Task.id).filter(Task.user_id == user_id)

    query = query.order_by(Conversation.updated_at.desc(), Conversation.id.asc())
    is_paged = limit is not None
    if is_paged:
        if skip: query = query.offset(skip)
        query = query.limit(min(limit, 100))
    else:
        count = query.count()
        if count > MAX_EXPORT_ROWS:
            raise HTTPException(400, f"导出数据量 ({count} 条) 超过上限 ({MAX_EXPORT_ROWS} 条)，请缩小筛选范围")
    rows = query.all()

    stage_map = {"qualifying": "触达", "nurturing": "培育", "converting": "转化", "follow_up": "跟进"}

    headers = ["对方昵称", "抖音号", "阶段", "最新消息", "消息总数", "最后发送时间"]
    data = [[
        r.recipient_nickname or "", r.recipient_douyin_id or "",
        stage_map.get(r.current_stage, r.current_stage or ""),
        r.last_dm_content or "", str(r.total_dm_count or 0),
        str(r.last_dm_at or "")
    ] for r in rows]

    buf = _build_xlsx(headers, data)
    return _stream_xlsx(f"conversations_{bj_now().strftime('%Y%m%d')}.xlsx", buf)
