"""Read models and export payloads for collected content data."""
import io
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import Integer, asc, cast, desc, func, or_

from app.config import bj_now
from app.db.models.content_collection import CollectedComment, CollectedUser, Conversation
from app.db_models import Device, Task


MAX_EXPORT_ROWS = 50000


def list_comments(
    db,
    user,
    keyword: Optional[str] = None,
    account_id: Optional[str] = None,
    search: Optional[str] = None,
    task_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
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
    if role != "admin":
        query = query.join(Task, CollectedComment.task_id == Task.id).filter(Task.user_id == user_id)
    query = query.order_by(CollectedComment.created_at.desc(), CollectedComment.id.asc())
    return _paginate(query, skip, limit)


def list_users(
    db,
    user,
    keyword: Optional[str] = None,
    account_id: Optional[str] = None,
    search: Optional[str] = None,
    task_id: Optional[str] = None,
    is_private: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "desc",
    skip: int = 0,
    limit: int = 50,
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
    if role != "admin":
        query = query.join(Task, CollectedUser.task_id == Task.id).filter(Task.user_id == user_id)
    if is_private == "yes":
        query = query.filter(CollectedUser.is_private == "是")
    elif is_private == "no":
        query = query.filter(or_(
            CollectedUser.is_private.is_(None),
            CollectedUser.is_private == "否",
        ))
    query = _apply_date_range(query, CollectedUser.created_at, date_from, date_to)
    query = _apply_user_sort(query, sort_by, sort_order)
    return _paginate(query, skip, limit)


def list_conversations(
    db,
    user,
    account_id: Optional[str] = None,
    stage: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    task_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
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
    if role != "admin":
        query = query.join(Task, Conversation.task_id == Task.id).filter(Task.user_id == user_id)
    query = query.order_by(Conversation.updated_at.desc(), Conversation.id.asc())
    return _paginate(query, skip, limit)


def export_comments(
    db,
    user,
    keyword: Optional[str] = None,
    account_id: Optional[str] = None,
    search: Optional[str] = None,
    task_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    skip: Optional[int] = None,
    limit: Optional[int] = None,
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
    query = _apply_date_range(query, CollectedComment.created_at, date_from, date_to)
    user_id, role = user
    if role != "admin":
        query = query.join(Task, CollectedComment.task_id == Task.id).filter(Task.user_id == user_id)
    query = query.order_by(CollectedComment.created_at.desc(), CollectedComment.id.asc())
    rows = _export_rows(query, skip, limit)

    headers = ["昵称", "内容", "AI回复", "关键词", "点赞数", "回复数", "IP属地", "意向省份", "意向城市", "意向景点", "是否作者", "评论时间", "采集时间"]
    data = [[
        r.nickname or "", r.content or "", r.ai_reply or "", r.keyword or "",
        r.like_count or "", r.reply_count or "", r.location or "",
        r.intended_province or "", r.intended_city or "", r.intended_attraction or "",
        "是" if r.is_author else "否", r.time_str or "", str(r.created_at or ""),
    ] for r in rows]

    return _stream_xlsx(f"comments_{bj_now().strftime('%Y%m%d')}.xlsx", _build_xlsx(headers, data))


def export_users(
    db,
    user,
    keyword: Optional[str] = None,
    account_id: Optional[str] = None,
    search: Optional[str] = None,
    task_id: Optional[str] = None,
    is_private: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "desc",
    skip: Optional[int] = None,
    limit: Optional[int] = None,
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
    query = _apply_date_range(query, CollectedUser.created_at, date_from, date_to)
    user_id, role = user
    if role != "admin":
        query = query.join(Task, CollectedUser.task_id == Task.id).filter(Task.user_id == user_id)
    query = _apply_user_sort(query, sort_by, sort_order)
    rows = _export_rows(query, skip, limit)

    headers = ["昵称", "抖音号", "关键词", "入口评论", "意向省份", "意向城市", "意向景点", "获赞", "关注", "粉丝", "作品", "性别", "年龄", "IP属地", "私密账号", "采集时间"]
    data = [[
        r.nickname or "", r.douyin_id or "", r.keyword or "", r.source_comment_content or "",
        r.intended_province or "", r.intended_city or "", r.intended_attraction or "",
        r.likes_count or "", r.follow_count or "", r.fans_count or "", r.works_count or "",
        r.gender or "", r.age or "", r.ip_location or "", r.is_private or "",
        str(r.created_at or ""),
    ] for r in rows]

    return _stream_xlsx(f"users_{bj_now().strftime('%Y%m%d')}.xlsx", _build_xlsx(headers, data))


def export_conversations(
    db,
    user,
    account_id: Optional[str] = None,
    stage: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    task_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    skip: Optional[int] = None,
    limit: Optional[int] = None,
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
    query = _apply_date_range(query, Conversation.created_at, date_from, date_to)
    user_id, role = user
    if role != "admin":
        query = query.join(Task, Conversation.task_id == Task.id).filter(Task.user_id == user_id)
    query = query.order_by(Conversation.updated_at.desc(), Conversation.id.asc())
    rows = _export_rows(query, skip, limit)

    stage_map = {"qualifying": "触达", "nurturing": "培育", "converting": "转化", "follow_up": "跟进"}
    headers = ["对方昵称", "抖音号", "阶段", "最新消息", "消息总数", "最后发送时间"]
    data = [[
        r.recipient_nickname or "", r.recipient_douyin_id or "",
        stage_map.get(r.current_stage, r.current_stage or ""),
        r.last_dm_content or "", str(r.total_dm_count or 0),
        str(r.last_dm_at or ""),
    ] for r in rows]

    return _stream_xlsx(f"conversations_{bj_now().strftime('%Y%m%d')}.xlsx", _build_xlsx(headers, data))


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


def _apply_date_range(query, column, date_from: Optional[str], date_to: Optional[str]):
    if date_from:
        try:
            query = query.filter(column >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            end = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(column <= end)
        except ValueError:
            pass
    return query


def _export_rows(query, skip: Optional[int], limit: Optional[int]):
    is_paged = limit is not None
    if is_paged:
        if skip:
            query = query.offset(skip)
        query = query.limit(min(limit, 100))
    else:
        count = query.count()
        if count > MAX_EXPORT_ROWS:
            raise HTTPException(400, f"导出数据量 ({count} 条) 超过上限 ({MAX_EXPORT_ROWS} 条)，请缩小筛选范围")
    return query.all()


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_like(pattern: str) -> str:
    return f"%{_escape_like(pattern)}%"


def _like_contains(column, value: str):
    return column.like(_build_like(value), escape="\\")


def _build_xlsx(headers: list[str], rows: list[list]) -> io.BytesIO:
    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet()
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def _stream_xlsx(filename: str, buffer: io.BytesIO) -> StreamingResponse:
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
