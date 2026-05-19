"""DM 私信序列模板 CRUD API."""
import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token, require_role, verify_device_secret
from app.db_models import DMSequence

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dm-sequences", tags=["dm-sequences"])


class SequenceMessage(BaseModel):
    order: int
    content: str = Field(..., min_length=1, max_length=500)
    delay_ms: int = Field(default=0, ge=0, le=60000)


class SequenceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    messages: list[SequenceMessage] = Field(..., min_length=1)
    industry: Optional[str] = None


class SequenceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    messages: Optional[list[SequenceMessage]] = Field(default=None, min_length=1)
    industry: Optional[str] = None


class DMSequenceGenerateRequest(BaseModel):
    industry: str = Field(default="general", description="行业key: health/beauty/education/travel/secondhand/general")
    description: str = Field(..., min_length=5, max_length=500, description="大白话描述")
    link_url: str = Field(..., min_length=5, max_length=500, description="消息2的短链URL")


class VariantsGenerateRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=5, description="生成变体套数")


def _to_dict(s: DMSequence) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "messages": s.messages,
        "message_count": len(s.messages),
        "industry": s.industry or "",
        "created_at": str(s.created_at) if s.created_at else None,
        "updated_at": str(s.updated_at) if s.updated_at else None,
    }


def _to_device_dict(s: DMSequence) -> dict:
    """Device-facing: only id + messages, minimal payload."""
    return {"id": s.id, "messages": s.messages}


@router.get("")
def list_sequences(
    industry: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: tuple = Depends(verify_admin_token),
):
    query = db.query(DMSequence)
    if industry:
        query = query.filter(DMSequence.industry == industry)
    sequences = query.order_by(DMSequence.updated_at.desc()).all()
    return {"sequences": [_to_dict(s) for s in sequences]}


@router.post("")
def create_sequence(
    body: SequenceCreate,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    # Auto-renumber: sort by order, assign 1,2,3...
    sorted_msgs = sorted(
        [{"order": i + 1, "content": m.content, "delay_ms": m.delay_ms}
         for i, m in enumerate(sorted(body.messages, key=lambda x: x.order))],
        key=lambda x: x["order"],
    )
    user_id, _ = user
    seq = DMSequence(
        name=body.name,
        messages=sorted_msgs,
        industry=body.industry or None,
        user_id=user_id,
    )
    db.add(seq)
    db.commit()
    db.refresh(seq)
    return _to_dict(seq)


@router.get("/{sequence_id}")
def get_sequence(
    sequence_id: str,
    db: Session = Depends(get_db),
    user: tuple = Depends(verify_admin_token),
):
    seq = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="序列模板不存在")
    return _to_dict(seq)


@router.put("/{sequence_id}")
def update_sequence(
    sequence_id: str,
    body: SequenceUpdate,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    seq = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="序列模板不存在")

    if body.name is not None:
        seq.name = body.name
    if body.messages is not None:
        seq.messages = [
            {"order": i + 1, "content": m.content, "delay_ms": m.delay_ms}
            for i, m in enumerate(sorted(body.messages, key=lambda x: x.order))
        ]
    if body.industry is not None:
        seq.industry = body.industry or None

    db.commit()
    db.refresh(seq)
    return _to_dict(seq)


@router.delete("/{sequence_id}")
def delete_sequence(
    sequence_id: str,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    seq = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="序列模板不存在")
    db.delete(seq)
    db.commit()
    return {"deleted": True, "id": sequence_id}


@router.post("/generate")
async def generate_dm_sequence(
    body: DMSequenceGenerateRequest,
    db: Session = Depends(get_db),
    current_user: tuple = Depends(require_role("admin")),
):
    """AI生成完整3条消息序列 (SSE流式)."""
    from app.services.industry_profile_service import load_profile
    from app.services.ai_generator import ai_generator as gen

    profile = load_profile(body.industry)

    system_prompt = profile["system_prompt"]
    sensitive_words_str = "、".join(profile["sensitive_words"])
    extreme_words_str = "、".join(profile["extreme_words"])
    style_guide = profile["style_guide"]

    user_prompt = (
        f"你是一个专业的私信话术生成助手。\n\n"
        f"## 行业约束\n"
        f"- 行业: {profile['label']}\n"
        f"- 话术风格: {style_guide}\n"
        f"- 绝对禁用词(包含任一词即不合格): {sensitive_words_str}\n"
        f"- 极限词禁用: {extreme_words_str}\n\n"
        f"## 平台规则\n"
        f"{system_prompt}\n\n"
        f"## 任务\n"
        f"根据用户描述生成3条私信消息序列:\n"
        f"- 消息1: 建立信任的钩子，吸引用户注意，让用户愿意继续看\n"
        f"- 消息2: 用户提供的链接地址（原样保留，不修改）\n"
        f"- 消息3: 驱动点击的收口CTA，引导用户点击消息2的链接\n\n"
        f"要求:\n"
        f"1. 每条消息50-150字，语气自然像真人聊天\n"
        f"2. 消息1和消息3需要针对私信场景设计，不能像广告文案\n"
        f"3. 不出现任何禁用词或极限词\n"
        f'4. 返回纯JSON数组: [{{"order":1,"content":"...","delay_ms":2000}},'
        f'{{"order":2,"content":"{body.link_url}","delay_ms":1500}},'
        f'{{"order":3,"content":"...","delay_ms":2000}}]\n'
        f"5. delay_ms: 消息1用2000, 消息2用1500, 消息3用2000\n\n"
        f"用户描述: {body.description}"
    )

    async def event_stream():
        label = profile.get("label", body.industry)
        yield f"data: {json.dumps({'type': 'status', 'text': f'AI 正在生成 {label} 行业序列...'})}\n\n"

        raw_chunks = []
        try:
            async for chunk in gen.generate_custom_stream(
                db, system_prompt, user_prompt, max_tokens=2048
            ):
                raw_chunks.append(chunk)
                yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"

            full = "".join(raw_chunks).strip()

            if full.startswith("```"):
                lines = full.split("\n")
                full = "\n".join(lines[1:])
                if full.endswith("```"):
                    full = full[: full.rfind("```")].strip()

            match = re.search(r"\[[\s\S]*\]", full)
            if not match:
                yield f"data: {json.dumps({'type': 'error', 'message': 'AI 返回格式异常，请重试'})}\n\n"
                return

            messages = json.loads(match.group())

            for msg in messages:
                content_text = msg.get("content", "")
                for word in profile["sensitive_words"]:
                    if word in content_text:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'生成内容含敏感词: {word}'})}\n\n"
                        return

            yield f"data: {json.dumps({'type': 'done', 'messages': messages})}\n\n"

        except json.JSONDecodeError:
            yield f"data: {json.dumps({'type': 'error', 'message': 'JSON 解析失败，请重试'})}\n\n"
        except Exception as e:
            logger.error("DM sequence generation failed: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': f'生成失败: {str(e)[:200]}'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{seq_id}/variants")
async def generate_variants(
    seq_id: str,
    body: VariantsGenerateRequest,
    db: Session = Depends(get_db),
    current_user: tuple = Depends(require_role("admin")),
):
    """基于已有messages生成N套变体."""
    from app.services.industry_profile_service import load_profile
    from app.services.ai_generator import ai_generator as gen

    seq = db.query(DMSequence).filter(DMSequence.id == seq_id).first()
    if not seq:
        raise HTTPException(404, "DM序列不存在")

    if not seq.messages or len(seq.messages) < 3:
        raise HTTPException(400, "DM序列至少需要3条消息才能生成变体")

    industry = getattr(seq, "industry", "general") or "general"
    profile = load_profile(industry)

    original_msg1 = (
        seq.messages[0].get("content", "")
        if isinstance(seq.messages[0], dict)
        else ""
    )
    original_msg2 = seq.messages[1]
    original_msg3 = (
        seq.messages[2].get("content", "")
        if len(seq.messages) > 2 and isinstance(seq.messages[2], dict)
        else ""
    )

    variant_system_prompt = (
        f"你是私信话术改写助手。遵守:\n"
        f"1. 保持原意不变\n"
        f"2. {profile['style_guide']}\n"
        f"3. 不使用禁用词和极限词\n"
        f"4. 语气自然如真人"
    )

    variants = []

    for vi in range(body.count):
        variant_prompt = (
            f"请对以下私信话术做同义改写，保持核心意思不变，换用不同的表达方式。\n\n"
            f"## 约束\n"
            f"- 禁用词: {'、'.join(profile['sensitive_words'][:20])}\n"
            f"- {profile['style_guide']}\n"
            f"- 每条50-150字\n"
            f"- 不要改变原意和核心信息\n"
            f"- 语气自然像真人\n\n"
            f"原始消息1(钩子): {original_msg1}\n"
            f"原始消息3(收口): {original_msg3}\n\n"
            f'返回JSON: {{"msg1": "改写后的消息1", "msg3": "改写后的消息3"}}'
        )

        try:
            response = await gen.generate_custom(
                db, variant_system_prompt, variant_prompt, max_tokens=1024
            )

            clean = response.strip()
            if clean.startswith("```"):
                lines = clean.split("\n")
                clean = "\n".join(lines[1:])
                if clean.endswith("```"):
                    clean = clean[: clean.rfind("```")].strip()

            match = re.search(r"\{[\s\S]*\}", clean)
            if match:
                result = json.loads(match.group())
            else:
                result = json.loads(clean)

            rewritten_msg1 = result.get("msg1", original_msg1)
            rewritten_msg3 = result.get("msg3", original_msg3)

            ok = True
            for word in profile["sensitive_words"]:
                if word in rewritten_msg1 or word in rewritten_msg3:
                    ok = False
                    break
            if not ok:
                continue

            variant = [
                {
                    "order": 1,
                    "content": rewritten_msg1,
                    "delay_ms": seq.messages[0].get("delay_ms", 2000),
                },
                original_msg2,
                {
                    "order": 3,
                    "content": rewritten_msg3,
                    "delay_ms": (
                        seq.messages[2].get("delay_ms", 2000)
                        if len(seq.messages) > 2
                        else 2000
                    ),
                },
            ]
            variants.append(variant)
        except Exception as e:
            logger.warning(
                "Variant generation attempt %d failed: %s", vi + 1, e
            )
            continue

    if not variants:
        raise HTTPException(500, "无法生成合规变体，请调整原始话术后重试")

    seq.variants = variants
    db.commit()

    return {"ok": True, "variants_count": len(variants), "variants": variants}


@router.get("/device/sync")
def device_sync(
    db: Session = Depends(get_db),
    _: str = Depends(verify_device_secret),
):
    """设备端同步全量 DM 序列模板（用于 poll 响应或独立拉取）"""
    sequences = db.query(DMSequence).all()
    return {"dm_sequences": [_to_device_dict(s) for s in sequences]}
