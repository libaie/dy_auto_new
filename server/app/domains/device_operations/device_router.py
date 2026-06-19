"""Device-facing API — poll, report, heartbeat, selectors."""
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models import (
    DeviceRegisterRequest,
    DeviceRegisterResponse, DeviceGenerateRequest, DeviceGenerateResponse,
    DeviceAIProxyRequest, DeviceAIProxyResponse,
    CollectReportRequest, CollectCommentData, CollectUserData,
    DMClaimRecipientRequest, DMClaimRecipientResponse,
    DMSendReportRequest, DMReleaseRecipientRequest, DMReleaseRecipientResponse,
)
from app.database import get_db
from app.deps import verify_device_secret
from app.config import ANTI_DETECT_CONFIG, ANTI_DETECT_CONFIG_VERSION, DEVICE_CONFIG, bj_now
from app.ws_manager import pair_ws_manager
from app.domains.device_operations import pairing, polling, reporting, script_assets, status_ws

router = APIRouter(prefix="/api/device", tags=["device"])

router.include_router(pairing.router)
router.include_router(status_ws.router)

router.include_router(polling.router)
router.include_router(reporting.router)



@router.post("/register", response_model=DeviceRegisterResponse)
def register_device(
    request: DeviceRegisterRequest,
    raw_request: Request,
    db: Session = Depends(get_db),
    authed_device_id: Optional[str] = Depends(verify_device_secret),
):
    # Per-device secret: reject mismatch
    if authed_device_id and authed_device_id != request.device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")
    from app.services.device_service import device_service
    from app.config import get_ai_config

    # Capture client IP
    client_ip = raw_request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip:
        client_ip = raw_request.client.host if raw_request.client else ""

    result = device_service.register(
        db=db, device_id=request.device_id, name=request.name,
        os_version=request.os_version, app_version=request.app_version,
        ip=client_ip,
        screen_resolution=request.screen_resolution,
        sdk_version=request.sdk_version,
        total_memory=request.total_memory,
        manufacturer=request.manufacturer,
        product=request.product,
        device_model=request.device_model,
        hardware=request.hardware,
        display=request.display,
    )

    # 组装完整设备配置
    config = {
        **DEVICE_CONFIG,
        "anti_detect_config": ANTI_DETECT_CONFIG,
        "anti_detect_config_version": ANTI_DETECT_CONFIG_VERSION,
    }
    ai_cfg = get_ai_config(db)
    if ai_cfg:
        config["ai_config"] = ai_cfg

    return DeviceRegisterResponse(
        device_id=result["device_id"],
        name=result["name"],
        status=result["status"],
        config=config,
    )


router.include_router(script_assets.router)
router.include_router(reporting.risk_router)

class CommentRepliedRequest(BaseModel):
    author: str = Field(..., description="评论作者")
    text: str = Field(..., description="评论内容")


@router.post("/comment-claim-reply")
def claim_comment_reply(
    request: CommentRepliedRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """原子操作：检查+标记。返回 claimed=true 表示该设备可以回复，false 表示已被其他设备占用"""
    import hashlib
    from sqlalchemy.exc import IntegrityError
    content_hash = hashlib.sha256(
        (request.author + "|" + request.text).encode("utf-8")
    ).hexdigest()
    from app.db_models import RepliedComment
    # INSERT first — PK collision triggers IntegrityError, no SELECT+INSERT race window
    db.add(RepliedComment(
        content_hash=content_hash,
        author=request.author,
        text=request.text,
        replied_by_device=authed_device_id,
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"claimed": False, "hash": content_hash}
    return {"claimed": True, "hash": content_hash}


@router.post("/comment-claim-release")
def release_comment_claim(
    request: CommentRepliedRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """回复失败时释放占位，避免误标记为已回复"""
    import hashlib
    content_hash = hashlib.sha256(
        (request.author + "|" + request.text).encode("utf-8")
    ).hexdigest()
    from app.db_models import RepliedComment
    db.query(RepliedComment).filter(
        RepliedComment.content_hash == content_hash,
        RepliedComment.replied_by_device == authed_device_id,
    ).delete()
    db.commit()
    return {"released": True}


@router.post("/generate-content", response_model=DeviceGenerateResponse)
async def generate_content(
    request: DeviceGenerateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    """Generate content from a template on-demand."""
    from app.services.content_service import content_service

    try:
        content = await content_service.generate_from_template(
            db, request.template_id, request.context,
        )
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail="Template not found")
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")

    return DeviceGenerateResponse(content=content, template_id=request.template_id)


router.include_router(script_assets.template_router)


@router.post("/ai-proxy", response_model=DeviceAIProxyResponse)
async def ai_proxy(
    request: DeviceAIProxyRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    """设备端 AI 代理 — 设备不持有 API Key，通过服务端调用 AI。"""
    import httpx
    from app.config import get_ai_config_with_key

    ai_cfg = get_ai_config_with_key(db)
    if not ai_cfg or not ai_cfg.get("api_url"):
        raise HTTPException(status_code=503, detail="AI service not configured")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            model = ai_cfg.get("model", "deepseek-chat")
            json_body = {
                "model": model,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "messages": [{"role": "user", "content": request.prompt}],
            }
            # thinking 参数仅在 deepseek-reasoner 或明确支持 thinking 的模型上发送
            if ai_cfg.get("thinking_enabled") and ("reasoner" in model.lower() or "r1" in model.lower()):
                json_body["thinking"] = {"type": "enabled"}
            logger.debug("AI proxy request: model=%s max_tokens=%s temp=%s prompt_len=%s thinking=%s",
                          model, request.max_tokens, request.temperature, len(request.prompt),
                          "thinking" in json_body)
            resp = await client.post(
                ai_cfg["api_url"],
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {ai_cfg.get('api_key', '')}",
                },
                json=json_body,
            )
        if resp.status_code != 200:
            logger.error("AI API error: status=%s body=%s", resp.status_code, resp.text[:500])
            raise HTTPException(status_code=502, detail=f"AI API error: {resp.status_code}")
        result = resp.json()
        logger.debug("AI API response: %s", {k: str(v)[:200] for k, v in result.items() if k != "choices"})
        content = (result.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        if not content:
            logger.error("AI API returned empty content. Full response: %s", str(result)[:1000])
        return DeviceAIProxyResponse(content=content)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI API timeout")
    except (KeyError, IndexError) as e:
        logger.error("Invalid AI response structure: %s", e)
        raise HTTPException(status_code=502, detail=f"Invalid AI response: {e}")

# --- 采集数据上报 ---


_dest_cache: dict[str, dict] = {}

async def _resolve_destination(keyword: str, db) -> dict | None:
    """服务端解析旅游关键词→省份/城市/景点，按 keyword 缓存。"""
    if not keyword or keyword in _dest_cache:
        return _dest_cache.get(keyword)
    from app.services.ai_generator import ai_generator
    try:
        raw = await ai_generator.generate_custom(
            db,
            "只输出 JSON，不要其他文本。",
            "将以下旅游关键词解析为目的地信息。\n关键词：" + keyword + "\n输出格式：{\"province\":\"省份\",\"city\":\"城市\",\"attraction\":\"景点\"}\n如果关键词本身是省份或城市，对应字段填空字符串。",
            max_tokens=200, temperature=0.1,
        )
        import json
        m = __import__("re").search(r'\{[\s\S]*\}', raw)
        if m:
            data = json.loads(m.group(0))
            _dest_cache[keyword] = data
            return data
    except Exception:
        pass
    _dest_cache[keyword] = None
    return None


@router.post("/collect-report")
async def collect_report(
    request: CollectReportRequest,
    db: Session = Depends(get_db),
    device_id: str = Depends(verify_device_secret),
):
    from app.db_models import CollectedComment, CollectedUser
    from sqlalchemy.exc import IntegrityError

    # 1. 解析目的地（设备端未传时服务端兜底，仅旅游行业任务触发）
    _is_travel = False
    has_dest = (request.comment.intended_province or request.comment.intended_city or request.comment.intended_attraction)
    if not has_dest and request.keyword and request.task_id:
        from app.db_models import Task
        task = db.query(Task).filter(Task.id == request.task_id).first()
        if task and task.params:
            tid = task.params.get("prompt_template_id")
            if tid:
                from app.db_models import PromptTemplate
                pt = db.query(PromptTemplate).filter(PromptTemplate.id == tid).first()
                _is_travel = pt and pt.industry == "travel"
    if _is_travel and not has_dest and request.keyword:
        dest = await _resolve_destination(request.keyword, db)
        if dest:
            if not request.comment.intended_province:
                request.comment.intended_province = dest.get("province")
            if not request.comment.intended_city:
                request.comment.intended_city = dest.get("city")
            if not request.comment.intended_attraction:
                request.comment.intended_attraction = dest.get("attraction")

    # 2. 保存评论（独立提交，用户去重失败不影响评论落库）
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
    db.commit()  # 评论独立提交

    # 2. 保存用户（存在则更新，不存在则新建）
    user_new = False
    user_douyin_id = ""
    user_nickname = ""
    if request.user:
        user_douyin_id = (request.user.douyin_id or "").strip()
        user_nickname = (request.user.nickname or "").strip()

    if request.user and user_douyin_id:
        existing = db.query(CollectedUser).filter(
            CollectedUser.douyin_id == user_douyin_id
        ).first()
        if existing:
            existing.nickname = user_nickname
            existing.likes_count = request.user.likes_count
            existing.follow_count = request.user.follow_count
            existing.fans_count = request.user.fans_count
            existing.works_count = request.user.works_count
            existing.gender = request.user.gender
            existing.age = request.user.age
            existing.ip_location = request.user.ip_location
            existing.is_private = request.user.is_private
            existing.data_source_type = request.data_source_type
            existing.keyword = request.keyword
            existing.source_comment_content = request.comment.content
            existing.task_id = request.task_id
            existing.device_id = device_id
            if request.comment.intended_province:
                existing.intended_province = request.comment.intended_province
            if request.comment.intended_city:
                existing.intended_city = request.comment.intended_city
            if request.comment.intended_attraction:
                existing.intended_attraction = request.comment.intended_attraction
            db.commit()
        else:
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
                user_new = True
            except IntegrityError:
                db.rollback()
                existing2 = db.query(CollectedUser).filter(
                    CollectedUser.douyin_id == user_douyin_id
                ).first()
                if existing2:
                    existing2.nickname = user_nickname
                    existing2.likes_count = request.user.likes_count
                    existing2.follow_count = request.user.follow_count
                    existing2.fans_count = request.user.fans_count
                    existing2.works_count = request.user.works_count
                    existing2.gender = request.user.gender
                    existing2.age = request.user.age
                    existing2.ip_location = request.user.ip_location
                    existing2.is_private = request.user.is_private
                    existing2.data_source_type = request.data_source_type
                    existing2.keyword = request.keyword
                    existing2.source_comment_content = request.comment.content
                    existing2.task_id = request.task_id
                    existing2.device_id = device_id
                    db.commit()

    # WS 实时推送
    await pair_ws_manager.broadcast_to_admins({"event": "data_changed", "type": "comment", "id": comment.id})
    if user_new:
        await pair_ws_manager.broadcast_to_admins({"event": "data_changed", "type": "user", "id": user_douyin_id})

    return {"comment_saved": True, "user_new": user_new}


# --- DM conversation endpoints ---

@router.post("/dm-claim-recipient", response_model=DMClaimRecipientResponse)
def dm_claim_recipient(
    request: DMClaimRecipientRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """原子占用：insert conversation where not exists (account_id, douyin_id).
    SQLite WAL 竞态：并发 SELECT 可能同时通过 → IntegrityError → claimed=false."""
    from app.db_models import Conversation
    from sqlalchemy.exc import IntegrityError
    from datetime import datetime, timezone, timedelta

    now = bj_now()

    # 清理孤儿 claim（超 30min 未发送）
    orphan_threshold = now - timedelta(minutes=30)
    db.query(Conversation).filter(
        Conversation.claimed_at.isnot(None),
        Conversation.claimed_at < orphan_threshold,
        Conversation.status == "active",
        Conversation.last_dm_at.is_(None),
    ).delete()
    db.flush()

    # 检查已有会话
    existing = db.query(Conversation).filter(
        Conversation.account_id == request.account_id,
        Conversation.recipient_douyin_id == request.recipient_douyin_id,
    ).first()
    if existing:
        return DMClaimRecipientResponse(claimed=False, conversation_id=None)

    conv = Conversation(
        task_id=None,
        account_id=request.account_id,
        device_id=authed_device_id,
        recipient_nickname=request.recipient_nickname,
        recipient_douyin_id=request.recipient_douyin_id,
        claimed_at=now,
    )
    db.add(conv)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return DMClaimRecipientResponse(claimed=False, conversation_id=None)

    db.refresh(conv)
    return DMClaimRecipientResponse(claimed=True, conversation_id=conv.id)


@router.post("/dm-send-report")
async def dm_send_report(
    request: DMSendReportRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """DM 发送成功后上报：更新 stage、content、计数"""
    from app.db_models import Conversation

    now = bj_now()
    conv = db.query(Conversation).filter(Conversation.id == request.conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    if conv.device_id != authed_device_id:
        raise HTTPException(status_code=403, detail="会话不属于此设备")

    conv.current_stage = request.stage
    conv.intent = request.intent
    conv.last_dm_content = request.content
    conv.last_dm_at = now
    conv.total_dm_count = (conv.total_dm_count or 0) + 1
    conv.claimed_at = None  # 清除 claim 标记
    if request.keyword and not conv.keyword:
        conv.keyword = request.keyword
    db.commit()

    await pair_ws_manager.broadcast_to_admins({
        "event": "data_changed", "type": "conversation", "id": conv.id,
    })
    return {"ok": True}


@router.post("/dm-release-recipient", response_model=DMReleaseRecipientResponse)
def dm_release_recipient(
    request: DMReleaseRecipientRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """DM 发送失败时释放占用。仅允许 claim 设备释放，防止误删其他设备的成功会话。"""
    from app.db_models import Conversation

    conv = db.query(Conversation).filter(
        Conversation.id == request.conversation_id,
        Conversation.device_id == authed_device_id,
        Conversation.last_dm_at.is_(None),  # 尚未成功发送过
    ).first()
    if conv:
        db.delete(conv)
        db.commit()
        return DMReleaseRecipientResponse(released=True)
    return DMReleaseRecipientResponse(released=False)


class CommentAIReplyRequest(BaseModel):
    nickname: str
    text: str
    ai_reply: str
    task_id: str | None = None
    intended_province: str | None = None
    intended_city: str | None = None
    intended_attraction: str | None = None


@router.post("/comment-ai-reply")
def save_comment_ai_reply(
    request: CommentAIReplyRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_device_secret),
):
    """保存 AI 生成的回复到采集的评论记录（按昵称+内容+task_id 匹配，避免跨视频错配）"""
    from app.db_models import CollectedComment
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


class UserProfileRequest(BaseModel):
    nickname: str
    douyin_id: str = ""
    fans_count: str = ""
    likes_count: str = ""
    follow_count: str = ""
    works_count: str = ""
    gender: str = ""
    age: str = ""
    ip_location: str = ""
    is_private: str = ""
    keyword: str = ""
    task_id: str = ""
    intended_province: str | None = None
    intended_city: str | None = None
    intended_attraction: str | None = None


@router.post("/user-profile")
def save_user_profile(
    request: UserProfileRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """保存采集到的用户主页数据，按 douyin_id 去重插入。"""
    from app.db_models import CollectedUser
    from sqlalchemy.exc import IntegrityError

    douyin_id = request.douyin_id.strip()
    if not douyin_id:
        return {"saved": False, "reason": "empty douyin_id"}

    existing = db.query(CollectedUser).filter(CollectedUser.douyin_id == douyin_id).first()
    if existing:
        # Update fields if they changed
        changed = False
        for field in ("nickname", "fans_count", "likes_count", "follow_count",
                       "works_count", "gender", "age", "ip_location", "is_private",
                       "keyword"):
            val = getattr(request, field, "") or ""
            if getattr(existing, field, None) != val:
                setattr(existing, field, val)
                changed = True
        for field in ("intended_province", "intended_city", "intended_attraction"):
            val = getattr(request, field, None)
            if val and getattr(existing, field, None) != val:
                setattr(existing, field, val)
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
            device_id=authed_device_id,
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


class UserAvatarRequest(BaseModel):
    douyin_id: str
    image_base64: str  # base64-encoded JPEG/PNG


@router.post("/user-avatar")
def upload_user_avatar(
    request: UserAvatarRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_device_secret),
):
    """上传用户头像裁剪图，保存到本地并关联 CollectedUser."""
    import base64
    import os
    from app.db_models import CollectedUser

    douyin_id = request.douyin_id.strip()
    if not douyin_id:
        return {"saved": False, "reason": "empty douyin_id"}

    user = db.query(CollectedUser).filter(CollectedUser.douyin_id == douyin_id).first()
    if not user:
        return {"saved": False, "reason": "user not found"}

    try:
        img_data = base64.b64decode(request.image_base64)
    except Exception:
        return {"saved": False, "reason": "invalid base64"}

    if len(img_data) > 512 * 1024:
        return {"saved": False, "reason": "image too large (>512KB)"}

    avatar_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    filename = f"{douyin_id}.jpg"
    filepath = os.path.join(avatar_dir, filename)
    with open(filepath, "wb") as f:
        f.write(img_data)

    user.avatar_url = f"/api/device/avatar/{douyin_id}"
    db.commit()
    return {"saved": True, "filename": filename, "size": len(img_data)}


@router.get("/avatar/{douyin_id}")
def get_user_avatar(douyin_id: str):
    """获取用户头像图片."""
    import os
    from fastapi.responses import FileResponse
    avatar_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "avatars")
    filepath = os.path.join(avatar_dir, f"{douyin_id}.jpg")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Avatar not found")
    return FileResponse(filepath, media_type="image/jpeg")

