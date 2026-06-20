"""DM recipient claim, send report, and release use cases."""
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.config import bj_now
from app.db.models.content_collection import Conversation
from app.domains.content_collection import realtime_events
from app.models import DMClaimRecipientResponse, DMReleaseRecipientResponse


def claim_recipient(db, request, device_id: str):
    now = bj_now()
    orphan_threshold = now - timedelta(minutes=30)
    db.query(Conversation).filter(
        Conversation.claimed_at.isnot(None),
        Conversation.claimed_at < orphan_threshold,
        Conversation.status == "active",
        Conversation.last_dm_at.is_(None),
    ).delete()
    db.flush()

    existing = db.query(Conversation).filter(
        Conversation.account_id == request.account_id,
        Conversation.recipient_douyin_id == request.recipient_douyin_id,
    ).first()
    if existing:
        return DMClaimRecipientResponse(claimed=False, conversation_id=None)

    conversation = Conversation(
        task_id=None,
        account_id=request.account_id,
        device_id=device_id,
        recipient_nickname=request.recipient_nickname,
        recipient_douyin_id=request.recipient_douyin_id,
        claimed_at=now,
    )
    db.add(conversation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return DMClaimRecipientResponse(claimed=False, conversation_id=None)

    db.refresh(conversation)
    return DMClaimRecipientResponse(claimed=True, conversation_id=conversation.id)


async def send_report(db, request, device_id: str):
    now = bj_now()
    conversation = db.query(Conversation).filter(Conversation.id == request.conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")
    if conversation.device_id != device_id:
        raise HTTPException(status_code=403, detail="会话不属于此设备")

    conversation.current_stage = request.stage
    conversation.intent = request.intent
    conversation.last_dm_content = request.content
    conversation.last_dm_at = now
    conversation.total_dm_count = (conversation.total_dm_count or 0) + 1
    conversation.claimed_at = None
    if request.keyword and not conversation.keyword:
        conversation.keyword = request.keyword
    db.commit()

    await realtime_events.broadcast_data_changed("conversation", conversation.id)
    return {"ok": True}


def release_recipient(db, request, device_id: str):
    conversation = db.query(Conversation).filter(
        Conversation.id == request.conversation_id,
        Conversation.device_id == device_id,
        Conversation.last_dm_at.is_(None),
    ).first()
    if conversation:
        db.delete(conversation)
        db.commit()
        return DMReleaseRecipientResponse(released=True)
    return DMReleaseRecipientResponse(released=False)
