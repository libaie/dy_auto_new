"""DM recipient claim, send report, and release use cases."""
import hashlib
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.config import bj_now
from app.db.models.content_collection import Conversation, ConversationMessage
from app.db.models.task_operations import Task
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
        has_sent_message = bool(existing.last_dm_at or (existing.total_dm_count or 0) > 0)
        if not has_sent_message:
            has_sent_message = db.query(ConversationMessage.id).filter(
                ConversationMessage.conversation_id == existing.id,
                ConversationMessage.status == "sent",
            ).first() is not None
        if has_sent_message or existing.claimed_at is not None:
            return DMClaimRecipientResponse(claimed=False, conversation_id=None)
        existing.device_id = device_id
        existing.recipient_nickname = request.recipient_nickname
        existing.claimed_at = now
        db.commit()
        return DMClaimRecipientResponse(claimed=True, conversation_id=existing.id)

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


def _resolve_report_task(db, conversation: Conversation, request, device_id: str | None):
    if not request.task_id:
        return None
    task = db.query(Task).filter(Task.id == request.task_id).first()
    if not task:
        raise HTTPException(status_code=400, detail="任务不存在")
    if task.account_id != conversation.account_id:
        raise HTTPException(status_code=403, detail="任务账号与会话不匹配")
    if device_id and task.device_id and task.device_id != device_id:
        raise HTTPException(status_code=403, detail="任务设备与会话设备不匹配")
    return task


def _fallback_message_key(conversation: Conversation, request, message_order: int) -> str:
    if request.message_key:
        return request.message_key
    if request.task_id and request.message_order:
        sequence_id = request.dm_sequence_id or "single"
        return f"{request.task_id}:{sequence_id}:{request.message_order}"
    digest = hashlib.sha256((request.content or "").encode("utf-8")).hexdigest()[:16]
    return f"legacy:{conversation.id}:{digest}"


async def send_report(db, request, device_id: str):
    try:
        conversation_id = _persist_send_report(db, request, device_id)
    except IntegrityError:
        db.rollback()
        conversation_id = _persist_send_report(db, request, device_id)

    await realtime_events.broadcast_data_changed("conversation", conversation_id)
    return {"ok": True}


def _persist_send_report(db, request, device_id: str) -> str:
    now = bj_now()
    conversation = db.query(Conversation).filter(Conversation.id == request.conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")
    if conversation.device_id != device_id:
        raise HTTPException(status_code=403, detail="会话不属于此设备")

    task = _resolve_report_task(db, conversation, request, device_id)
    status = (request.status or "sent").lower()
    message_order = request.message_order or ((conversation.total_dm_count or 0) + 1)
    message_key = _fallback_message_key(conversation, request, message_order)

    message = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conversation.id,
        ConversationMessage.message_key == message_key,
    ).first()
    if not message:
        message = ConversationMessage(
            conversation_id=conversation.id,
            task_id=task.id if task else None,
            device_id=device_id,
            dm_sequence_id=request.dm_sequence_id,
            message_order=message_order,
            message_key=message_key,
            content=request.content,
            status=status,
            error_message=request.error_message,
            sent_at=now if status == "sent" else None,
        )
        db.add(message)
    else:
        message.task_id = task.id if task else message.task_id
        message.device_id = device_id
        message.dm_sequence_id = request.dm_sequence_id or message.dm_sequence_id
        message.message_order = request.message_order or message.message_order
        if not (message.status == "sent" and status != "sent"):
            message.content = request.content
            message.status = status
            message.error_message = request.error_message
            if status == "sent" and message.sent_at is None:
                message.sent_at = now

    conversation.current_stage = request.stage
    conversation.intent = request.intent
    conversation.claimed_at = None
    if task:
        conversation.task_id = task.id
    if request.keyword and not conversation.keyword:
        conversation.keyword = request.keyword
    if status == "sent":
        conversation.last_dm_content = request.content
        conversation.last_dm_at = message.sent_at or now

    db.flush()
    conversation.total_dm_count = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conversation.id,
        ConversationMessage.status == "sent",
    ).count()
    db.commit()
    return conversation.id


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
