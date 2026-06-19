"""Temporary device-authenticated bridge routes for content, collection, DM, and user data."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_device_secret
from app.domains.content_collection import collection_reports, content_generation, dm_claims
from app.models import (
    CollectReportRequest,
    DeviceAIProxyRequest,
    DeviceAIProxyResponse,
    DeviceGenerateRequest,
    DeviceGenerateResponse,
    DMClaimRecipientRequest,
    DMClaimRecipientResponse,
    DMReleaseRecipientRequest,
    DMReleaseRecipientResponse,
    DMSendReportRequest,
)

logger = logging.getLogger(__name__)
pre_template_router = APIRouter()
router = APIRouter()


class CommentRepliedRequest(BaseModel):
    author: str = Field(..., description="评论作者")
    text: str = Field(..., description="评论内容")


@pre_template_router.post("/comment-claim-reply")
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


@pre_template_router.post("/comment-claim-release")
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


@pre_template_router.post("/generate-content", response_model=DeviceGenerateResponse)
async def generate_content(
    request: DeviceGenerateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    """Generate content from a template on-demand."""
    try:
        content = await content_generation.generate_from_template(db, request)
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail="Template not found")
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")

    return DeviceGenerateResponse(content=content, template_id=request.template_id)

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

@router.post("/collect-report")
async def collect_report(
    request: CollectReportRequest,
    db: Session = Depends(get_db),
    device_id: str = Depends(verify_device_secret),
):
    return await collection_reports.collect_report(db, request, device_id)

# --- DM conversation endpoints ---

@router.post("/dm-claim-recipient", response_model=DMClaimRecipientResponse)
def dm_claim_recipient(
    request: DMClaimRecipientRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    return dm_claims.claim_recipient(db, request, authed_device_id)

@router.post("/dm-send-report")
async def dm_send_report(
    request: DMSendReportRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    return await dm_claims.send_report(db, request, authed_device_id)

@router.post("/dm-release-recipient", response_model=DMReleaseRecipientResponse)
def dm_release_recipient(
    request: DMReleaseRecipientRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    return dm_claims.release_recipient(db, request, authed_device_id)

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
    return collection_reports.save_comment_ai_reply(db, request)

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
    return collection_reports.save_user_profile(db, request, authed_device_id)

class UserAvatarRequest(BaseModel):
    douyin_id: str
    image_base64: str  # base64-encoded JPEG/PNG


@router.post("/user-avatar")
def upload_user_avatar(
    request: UserAvatarRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_device_secret),
):
    return collection_reports.upload_user_avatar(db, request)

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

