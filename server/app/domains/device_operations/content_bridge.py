"""设备运营业务域模块。

设备运营业务域，负责设备接入、脚本下发、轮询上报和状态生命周期。本文件负责 content_bridge 相关业务规则、状态转换和外部系统边界。
"""

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
    """业务类：承载 CommentRepliedRequest 相关的数据结构、状态或业务协作。

    类参数：author、text 承载该类的业务配置、状态或数据字段。
    """
    author: str = Field(..., description="评论作者")
    text: str = Field(..., description="评论内容")


@pre_template_router.post("/comment-claim-reply")
def claim_comment_reply(
    request: CommentRepliedRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """业务函数：处理 claim_comment_reply 对应的业务流程、校验或数据转换。

    入参：request、db、authed_device_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    import hashlib
    from sqlalchemy.exc import IntegrityError
    content_hash = hashlib.sha256(
        (request.author + "|" + request.text).encode("utf-8")
    ).hexdigest()
    from app.db.models.content_collection import RepliedComment
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
    """业务函数：处理 release_comment_claim 对应的业务流程、校验或数据转换。

    入参：request、db、authed_device_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    import hashlib
    content_hash = hashlib.sha256(
        (request.author + "|" + request.text).encode("utf-8")
    ).hexdigest()
    from app.db.models.content_collection import RepliedComment
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
    """业务函数：处理 generate_content 对应的业务流程、校验或数据转换。

    入参：request、db、_ 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 ai_proxy 对应的业务流程、校验或数据转换。

    入参：request、db、_ 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    from app.domains.model_configuration.ai_generator import ai_generator

    try:
        content = await ai_generator.generate_custom(
            db,
            "你是一个简洁、可靠的中文助手。直接回答用户请求。",
            request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        return DeviceAIProxyResponse(content=content)
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured") from e
        raise HTTPException(status_code=502, detail=f"AI service error: {e}") from e

@router.post("/collect-report")
async def collect_report(
    request: CollectReportRequest,
    db: Session = Depends(get_db),
    device_id: str = Depends(verify_device_secret),
):
    """业务函数：处理 collect_report 对应的业务流程、校验或数据转换。

    入参：request、db、device_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return await collection_reports.collect_report(db, request, device_id)

# --- DM conversation endpoints ---

@router.post("/dm-claim-recipient", response_model=DMClaimRecipientResponse)
def dm_claim_recipient(
    request: DMClaimRecipientRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """业务函数：处理 dm_claim_recipient 对应的业务流程、校验或数据转换。

    入参：request、db、authed_device_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return dm_claims.claim_recipient(db, request, authed_device_id)

@router.post("/dm-send-report")
async def dm_send_report(
    request: DMSendReportRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """业务函数：处理 dm_send_report 对应的业务流程、校验或数据转换。

    入参：request、db、authed_device_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return await dm_claims.send_report(db, request, authed_device_id)

@router.post("/dm-release-recipient", response_model=DMReleaseRecipientResponse)
def dm_release_recipient(
    request: DMReleaseRecipientRequest,
    db: Session = Depends(get_db),
    authed_device_id: str = Depends(verify_device_secret),
):
    """业务函数：处理 dm_release_recipient 对应的业务流程、校验或数据转换。

    入参：request、db、authed_device_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return dm_claims.release_recipient(db, request, authed_device_id)

class CommentAIReplyRequest(BaseModel):
    """业务类：承载 CommentAIReplyRequest 相关的数据结构、状态或业务协作。

    类参数：ai_reply、intended_attraction、intended_city、intended_province、nickname、task_id、text 承载该类的业务配置、状态或数据字段。
    """
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
    """业务函数：处理 save_comment_ai_reply 对应的业务流程、校验或数据转换。

    入参：request、db、_ 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return collection_reports.save_comment_ai_reply(db, request)

class UserProfileRequest(BaseModel):
    """业务类：承载 UserProfileRequest 相关的数据结构、状态或业务协作。

    类参数：age、douyin_id、fans_count、follow_count、gender、intended_attraction、intended_city、intended_province、ip_location、is_private、keyword、likes_count、nickname、task_id、works_count 承载该类的业务配置、状态或数据字段。
    """
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
    """业务函数：处理 save_user_profile 对应的业务流程、校验或数据转换。

    入参：request、db、authed_device_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return collection_reports.save_user_profile(db, request, authed_device_id)

class UserAvatarRequest(BaseModel):
    """业务类：承载 UserAvatarRequest 相关的数据结构、状态或业务协作。

    类参数：douyin_id、image_base64 承载该类的业务配置、状态或数据字段。
    """
    douyin_id: str
    image_base64: str  # base64-encoded JPEG/PNG


@router.post("/user-avatar")
def upload_user_avatar(
    request: UserAvatarRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_device_secret),
):
    """业务函数：处理 upload_user_avatar 对应的业务流程、校验或数据转换。

    入参：request、db、_ 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return collection_reports.upload_user_avatar(db, request)

@router.get("/avatar/{douyin_id}")
def get_user_avatar(douyin_id: str):
    """业务函数：处理 get_user_avatar 对应的业务流程、校验或数据转换。

    入参：douyin_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    import os
    from fastapi.responses import FileResponse
    avatar_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "avatars")
    filepath = os.path.join(avatar_dir, f"{douyin_id}.jpg")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Avatar not found")
    return FileResponse(filepath, media_type="image/jpeg")
