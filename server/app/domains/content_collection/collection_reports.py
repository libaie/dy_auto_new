"""内容采集业务域模块。

内容采集业务域，负责采集数据、私信序列、内容生成和实时事件。本文件负责 collection_reports 相关业务规则、状态转换和外部系统边界。
"""

import base64
import os

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.config import bj_now
from app.db.models.content_collection import CollectedComment, CollectedUser
from app.domains.content_collection import realtime_events


_dest_cache: dict[str, dict] = {}


async def collect_report(db, request, device_id: str):
    await _apply_travel_destination_fallback(db, request)

    comment = CollectedComment(
        task_id=request.task_id,
        device_id=device_id,
        keyword=request.keyword,
        nickname=request.comment.nickname,
        content=request.comment.content,
        time_str=request.comment.time_str,
        reply_count=request.comment.reply_count,
        like_count=request.comment.like_count,
        dislike_count=request.comment.dislike_count,
        location=request.comment.location,
        is_author=request.comment.is_author,
        data_source_type=request.data_source_type,
        ai_reply=request.comment.ai_reply,
        ai_replied_at=bj_now() if request.comment.ai_reply else None,
        intended_province=request.comment.intended_province or None,
        intended_city=request.comment.intended_city or None,
        intended_attraction=request.comment.intended_attraction or None,
    )
    db.add(comment)
    db.commit()

    user_new = _upsert_collected_user(db, request, device_id)
    await realtime_events.broadcast_data_changed("comment", comment.id)
    if user_new:
        await realtime_events.broadcast_data_changed("user", request.user.douyin_id.strip())

    return {"comment_saved": True, "user_new": user_new}


def save_comment_ai_reply(db, request):
    query = db.query(CollectedComment).filter(
        CollectedComment.nickname == request.nickname,
        CollectedComment.content == request.text,
        CollectedComment.ai_reply.is_(None),
    )
    if request.task_id:
        query = query.filter(CollectedComment.task_id == request.task_id)
    comment = query.order_by(CollectedComment.created_at.desc()).first()
    if comment:
        comment.ai_reply = request.ai_reply
        comment.ai_replied_at = bj_now()
        if request.intended_province is not None:
            comment.intended_province = request.intended_province
        if request.intended_city is not None:
            comment.intended_city = request.intended_city
        if request.intended_attraction is not None:
            comment.intended_attraction = request.intended_attraction
        db.commit()
        return {"updated": True}
    return {"updated": False}


def save_user_profile(db, request, device_id: str):
    douyin_id = request.douyin_id.strip()
    if not douyin_id:
        return {"saved": False, "reason": "empty douyin_id"}

    existing = db.query(CollectedUser).filter(CollectedUser.douyin_id == douyin_id).first()
    if existing:
        changed = False
        for field in (
            "nickname", "fans_count", "likes_count", "follow_count",
            "works_count", "gender", "age", "ip_location", "is_private",
            "keyword",
        ):
            value = getattr(request, field, "") or ""
            if getattr(existing, field, None) != value:
                setattr(existing, field, value)
                changed = True
        for field in ("intended_province", "intended_city", "intended_attraction"):
            value = getattr(request, field, None)
            if value and getattr(existing, field, None) != value:
                setattr(existing, field, value)
                changed = True
        if changed:
            db.commit()
        return {"saved": True, "updated": changed, "user_id": existing.id}

    try:
        user = CollectedUser(
            nickname=request.nickname,
            douyin_id=douyin_id,
            keyword=request.keyword or "",
            task_id=request.task_id or None,
            fans_count=request.fans_count or "",
            likes_count=request.likes_count or "",
            follow_count=request.follow_count or "",
            works_count=request.works_count or "",
            gender=request.gender or "",
            age=request.age or "",
            ip_location=request.ip_location or "",
            is_private=request.is_private or "",
            device_id=device_id,
            intended_province=request.intended_province or None,
            intended_city=request.intended_city or None,
            intended_attraction=request.intended_attraction or None,
        )
        db.add(user)
        db.commit()
        return {"saved": True, "updated": False, "user_id": user.id}
    except IntegrityError:
        db.rollback()
        return {"saved": False, "reason": "duplicate douyin_id"}


def upload_user_avatar(db, request):
    douyin_id = request.douyin_id.strip()
    if not douyin_id:
        return {"saved": False, "reason": "empty douyin_id"}

    user = db.query(CollectedUser).filter(CollectedUser.douyin_id == douyin_id).first()
    if not user:
        return {"saved": False, "reason": "user not found"}

    try:
        image_data = base64.b64decode(request.image_base64)
    except Exception:
        return {"saved": False, "reason": "invalid base64"}

    if len(image_data) > 512 * 1024:
        return {"saved": False, "reason": "image too large (>512KB)"}

    avatar_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    filename = f"{douyin_id}.jpg"
    filepath = os.path.join(avatar_dir, filename)
    with open(filepath, "wb") as file:
        file.write(image_data)

    user.avatar_url = f"/api/device/avatar/{douyin_id}"
    db.commit()
    return {"saved": True, "filename": filename, "size": len(image_data)}


async def _apply_travel_destination_fallback(db, request):
    is_travel = False
    has_destination = (
        request.comment.intended_province
        or request.comment.intended_city
        or request.comment.intended_attraction
    )
    if not has_destination and request.keyword and request.task_id:
        from app.db.models.prompt_management import PromptTemplate
        from app.db.models import Task
        task = db.query(Task).filter(Task.id == request.task_id).first()
        if task and task.params:
            template_id = task.params.get("prompt_template_id")
            if template_id:
                template = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()
                is_travel = template and template.industry == "travel"
    if is_travel and not has_destination and request.keyword:
        destination = await _resolve_destination(request.keyword, db)
        if destination:
            if not request.comment.intended_province:
                request.comment.intended_province = destination.get("province")
            if not request.comment.intended_city:
                request.comment.intended_city = destination.get("city")
            if not request.comment.intended_attraction:
                request.comment.intended_attraction = destination.get("attraction")


async def _resolve_destination(keyword: str, db) -> dict | None:
    if not keyword or keyword in _dest_cache:
        return _dest_cache.get(keyword)
    from app.domains.model_configuration.ai_generator import ai_generator
    try:
        raw = await ai_generator.generate_custom(
            db,
            "只输出 JSON，不要其他文本。",
            "将以下旅游关键词解析为目的地信息。\n关键词：" + keyword + "\n输出格式：{\"province\":\"省份\",\"city\":\"城市\",\"attraction\":\"景点\"}\n如果关键词本身是省份或城市，对应字段填空字符串。",
            max_tokens=200,
            temperature=0.1,
        )
        import json
        import re
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            data = json.loads(match.group(0))
            _dest_cache[keyword] = data
            return data
    except Exception:
        pass
    _dest_cache[keyword] = None
    return None


def _upsert_collected_user(db, request, device_id: str) -> bool:
    if not request.user:
        return False
    user_douyin_id = (request.user.douyin_id or "").strip()
    user_nickname = (request.user.nickname or "").strip()
    if not user_douyin_id:
        return False

    existing = db.query(CollectedUser).filter(
        CollectedUser.douyin_id == user_douyin_id
    ).first()
    if existing:
        _apply_user_fields(existing, request, user_nickname, device_id)
        db.commit()
        return False

    db.add(CollectedUser(
        task_id=request.task_id,
        device_id=device_id,
        keyword=request.keyword,
        source_comment_content=request.comment.content,
        nickname=user_nickname,
        douyin_id=user_douyin_id,
        likes_count=request.user.likes_count,
        follow_count=request.user.follow_count,
        fans_count=request.user.fans_count,
        works_count=request.user.works_count,
        gender=request.user.gender,
        age=request.user.age,
        ip_location=request.user.ip_location,
        is_private=request.user.is_private,
        data_source_type=request.data_source_type,
        intended_province=request.comment.intended_province or None,
        intended_city=request.comment.intended_city or None,
        intended_attraction=request.comment.intended_attraction or None,
    ))
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        existing = db.query(CollectedUser).filter(
            CollectedUser.douyin_id == user_douyin_id
        ).first()
        if existing:
            _apply_user_fields(existing, request, user_nickname, device_id)
            db.commit()
        return False


def _apply_user_fields(user, request, nickname: str, device_id: str):
    user.nickname = nickname
    user.likes_count = request.user.likes_count
    user.follow_count = request.user.follow_count
    user.fans_count = request.user.fans_count
    user.works_count = request.user.works_count
    user.gender = request.user.gender
    user.age = request.user.age
    user.ip_location = request.user.ip_location
    user.is_private = request.user.is_private
    user.data_source_type = request.data_source_type
    user.keyword = request.keyword
    user.source_comment_content = request.comment.content
    user.task_id = request.task_id
    user.device_id = device_id
    if request.comment.intended_province:
        user.intended_province = request.comment.intended_province
    if request.comment.intended_city:
        user.intended_city = request.comment.intended_city
    if request.comment.intended_attraction:
        user.intended_attraction = request.comment.intended_attraction
