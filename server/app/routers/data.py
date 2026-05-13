"""Data center admin API — collected comments, users, conversations."""
import io
from fastapi import APIRouter, Query, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from openpyxl import Workbook

from app.database import get_db
from app.deps import verify_admin_token
from app.config import bj_now
from app.db_models import CollectedComment, CollectedUser, Conversation, Device

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
    query = db.query(CollectedUser)
    if keyword:
        query = query.filter(CollectedUser.keyword == keyword)
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


# === Export endpoints ===

MAX_EXPORT_ROWS = 50000


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards to prevent accidental full-table matches."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_like(pattern: str) -> str:
    return f"%{_escape_like(pattern)}%"


@router.get("/export/comments")
def export_comments(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    skip: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    query = db.query(CollectedComment)
    if keyword:
        query = query.filter(CollectedComment.keyword == keyword)
    if account_id:
        device_ids = db.query(Device.id).filter(Device.bound_account_id == account_id).subquery()
        query = query.filter(CollectedComment.device_id.in_(device_ids))
    if search:
        pattern = _build_like(search)
        query = query.filter(or_(
            CollectedComment.nickname.like(pattern),
            CollectedComment.content.like(pattern),
        ))
    if task_id:
        query = query.filter(CollectedComment.task_id == task_id)

    query = query.order_by(CollectedComment.created_at.desc())
    is_paged = limit is not None
    if is_paged:
        if skip: query = query.offset(skip)
        query = query.limit(min(limit, 100))
    else:
        count = query.count()
        if count > MAX_EXPORT_ROWS:
            raise HTTPException(400, f"导出数据量 ({count} 条) 超过上限 ({MAX_EXPORT_ROWS} 条)，请缩小筛选范围")
    rows = query.all()

    headers = ["昵称", "内容", "AI回复", "关键词", "点赞数", "回复数", "IP属地", "是否作者", "评论时间", "采集时间"]
    data = [[
        r.nickname or "", r.content or "", r.ai_reply or "", r.keyword or "",
        r.like_count or "", r.reply_count or "", r.location or "",
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
    skip: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    query = db.query(CollectedUser)
    if keyword:
        query = query.filter(CollectedUser.keyword == keyword)
    if account_id:
        device_ids = db.query(Device.id).filter(Device.bound_account_id == account_id).subquery()
        query = query.filter(CollectedUser.device_id.in_(device_ids))
    if search:
        pattern = _build_like(search)
        query = query.filter(or_(
            CollectedUser.nickname.like(pattern),
            CollectedUser.douyin_id.like(pattern),
        ))
    if task_id:
        query = query.filter(CollectedUser.task_id == task_id)

    query = query.order_by(CollectedUser.created_at.desc())
    is_paged = limit is not None
    if is_paged:
        if skip: query = query.offset(skip)
        query = query.limit(min(limit, 100))
    else:
        count = query.count()
        if count > MAX_EXPORT_ROWS:
            raise HTTPException(400, f"导出数据量 ({count} 条) 超过上限 ({MAX_EXPORT_ROWS} 条)，请缩小筛选范围")
    rows = query.all()

    headers = ["昵称", "抖音号", "关键词", "获赞", "关注", "粉丝", "作品", "性别", "年龄", "IP属地", "私密账号", "采集时间"]
    data = [[
        r.nickname or "", r.douyin_id or "", r.keyword or "",
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
    skip: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    query = db.query(Conversation)
    if account_id:
        query = query.filter(Conversation.account_id == account_id)
    if stage:
        query = query.filter(Conversation.current_stage == stage)
    if status:
        query = query.filter(Conversation.status == status)
    if search:
        pattern = _build_like(search)
        query = query.filter(or_(
            Conversation.recipient_nickname.like(pattern),
            Conversation.last_dm_content.like(pattern),
            Conversation.recipient_douyin_id.like(pattern),
        ))
    if task_id:
        query = query.filter(Conversation.task_id == task_id)

    query = query.order_by(Conversation.last_dm_at.desc().nullslast())
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
