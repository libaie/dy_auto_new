"""DM 私信序列模板 CRUD API."""
import json
import logging
import random
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token, require_role, verify_device_secret
from app.db_models import DMSequence
from app.services.dm_sequence_visibility import get_device_visible_dm_sequences


def _jitter(delay_ms: int) -> int:
    """Apply ±25% random jitter to break fixed timing fingerprint across devices."""
    if delay_ms <= 0:
        return delay_ms
    delta = int(delay_ms * 0.25)
    return max(0, delay_ms + random.randint(-delta, delta))


def _jitter_messages(messages: list[dict]) -> list[dict]:
    """Return a shallow copy of messages with jittered delay_ms values."""
    return [
        {**m, "delay_ms": _jitter(m.get("delay_ms", 0))}
        for m in messages
    ]


def _variant_delay_ms() -> int:
    return random.randint(1500, 3000)


def _randomize_variant_delays(variant: list[dict]) -> list[dict]:
    return [{**message, "delay_ms": _variant_delay_ms()} for message in variant]


def _randomize_variants(variants: list[list[dict]]) -> list[list[dict]]:
    return [_randomize_variant_delays(variant) for variant in variants]


def _robust_parse_variant_json(raw: str) -> dict | None:
    """Extract and parse JSON from AI response, correcting common LLM formatting errors.

    Handles: markdown code fences, key typos (msg_1→msg1, message1→msg1, etc.),
    and trailing markdown artifacts.
    """
    if not raw:
        return None

    clean = raw.strip()

    # Strip markdown code fences (any language tag)
    fence_match = re.match(r"```(?:\w+)?\s*\n?(.*?)```", clean, re.DOTALL)
    if fence_match:
        clean = fence_match.group(1).strip()
    elif clean.startswith("```"):
        lines = clean.split("\n")
        if len(lines) > 1:
            clean = "\n".join(lines[1:])
        if clean.endswith("```"):
            clean = clean[:clean.rfind("```")].strip()

    # Extract JSON object — greedy match for outermost braces
    match = re.search(r"\{[\s\S]*\}", clean)
    if not match:
        return None
    candidate = match.group()

    # Known key typos from LLM outputs — normalize before parsing
    _key_fixes = [
        ("msg_1", "msg1"), ("msg_3", "msg3"),
        ("message1", "msg1"), ("message3", "msg3"),
        ("message_1", "msg1"), ("message_3", "msg3"),
        ("hook", "msg1"), ("cta", "msg3"),
    ]

    result = None
    # Attempt 1: parse as-is
    try:
        result = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        pass

    # Attempt 2: parse after key correction
    if result is None:
        fixed = candidate
        for wrong, right in _key_fixes:
            fixed = fixed.replace(f'"{wrong}"', f'"{right}"')
        try:
            result = json.loads(fixed)
        except (json.JSONDecodeError, TypeError):
            return None

    # Post-parse normalization: remap known wrong keys in a successfully-parsed dict
    for wrong, right in _key_fixes:
        if wrong in result:
            result[right] = result.pop(wrong)

    # Ensure at least one expected key exists
    if not result or ("msg1" not in result and "msg3" not in result):
        return None
    return result


def _normalize_generated_sequence_messages(messages: list) -> list[dict]:
    """Normalize common LLM key variants to the frontend SequenceMessage shape."""
    normalized = []
    for idx, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise ValueError("AI 返回的消息格式异常")
        content = (
            msg.get("content")
            or msg.get("message")
            or msg.get("text")
            or msg.get("msg")
        )
        if not isinstance(content, str) or not content.strip():
            raise ValueError("AI 返回的消息缺少内容字段")
        normalized.append({
            "order": int(msg.get("order") or idx + 1),
            "content": content.strip(),
            "delay_ms": int(msg.get("delay_ms") or msg.get("delayMs") or 0),
        })
    return normalized

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
    variants: Optional[list] = None


class DMSequenceGenerateRequest(BaseModel):
    industry: str = Field(default="general", description="行业key: health/beauty/education/travel/secondhand/general")
    description: str = Field(..., min_length=5, max_length=500, description="大白话描述")
    link_url: str = Field(..., min_length=5, max_length=500, description="消息2的短链URL")


class VariantsGenerateRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=20, description="生成变体套数")


def _to_dict(s: DMSequence) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "messages": s.messages,
        "message_count": len(s.messages),
        "industry": s.industry or "",
        "variants_count": len(s.variants) if s.variants else 0,
        "variants": s.variants,
        "created_at": str(s.created_at) if s.created_at else None,
        "updated_at": str(s.updated_at) if s.updated_at else None,
    }


def _to_device_dict(s: DMSequence) -> dict:
    """Device-facing: id + messages + variants for poll/sync.
    Applies ±25% jitter to base messages and 1500-3000ms random delays to variants."""
    msgs = _jitter_messages(s.messages) if s.messages else None
    vars_ = _randomize_variants(s.variants) if s.variants else None
    return {"id": s.id, "messages": msgs, "variants": vars_}


@router.get("")
def list_sequences(
    industry: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: tuple = Depends(verify_admin_token),
):
    user_id, _ = user
    query = db.query(DMSequence).filter(
        (DMSequence.user_id == user_id) | (DMSequence.user_id == None)
    )
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
    user_id, _ = user
    seq = db.query(DMSequence).filter(
        DMSequence.id == sequence_id,
        (DMSequence.user_id == user_id) | (DMSequence.user_id == None),
    ).first()
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
    user_id, _ = user
    seq = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="序列模板不存在")
    if seq.user_id and seq.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权修改其他用户的序列模板")

    if body.name is not None:
        seq.name = body.name
    if body.messages is not None:
        new_messages = [
            {"order": i + 1, "content": m.content, "delay_ms": m.delay_ms}
            for i, m in enumerate(sorted(body.messages, key=lambda x: x.order))
        ]
        # 只有消息内容/延迟实际变化时才清除旧变体
        if new_messages != seq.messages:
            seq.variants = None
        seq.messages = new_messages
    if body.industry is not None:
        old_industry = seq.industry
        seq.industry = body.industry or None
        if body.industry != (old_industry or None):
            seq.variants = None  # 行业变了，合规约束不同，旧变体失效
    if body.variants is not None:
        seq.variants = body.variants

    db.commit()
    db.refresh(seq)
    return _to_dict(seq)


@router.delete("/{sequence_id}")
def delete_sequence(
    sequence_id: str,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    user_id, _ = user
    seq = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="序列模板不存在")
    if seq.user_id and seq.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权删除其他用户的序列模板")
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

            messages = _normalize_generated_sequence_messages(json.loads(match.group()))

            for msg in messages:
                content_text = msg.get("content", "")
                for word in profile["sensitive_words"]:
                    if word in content_text:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'生成内容含敏感词: {word}'})}\n\n"
                        return
                for word in profile["extreme_words"]:
                    if word in content_text:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'生成内容含极限词: {word}'})}\n\n"
                        return

            messages = _jitter_messages(messages)
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

            result = _robust_parse_variant_json(response)
            if not result:
                logger.warning("Variant attempt %d JSON parse failed, skipping", vi + 1)
                continue

            rewritten_msg1 = result.get("msg1", original_msg1)
            rewritten_msg3 = result.get("msg3", original_msg3)

            ok = True
            for word in profile["sensitive_words"]:
                if word in rewritten_msg1 or word in rewritten_msg3:
                    ok = False
                    break
            if ok:
                for word in profile["extreme_words"]:
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
            variants.append(_randomize_variant_delays(variant))
        except Exception as e:
            logger.warning(
                "Variant generation attempt %d failed: %s", vi + 1, e
            )
            continue

    if not variants:
        raise HTTPException(500, "无法生成合规变体，请调整原始话术后重试")

    seq.variants = (seq.variants or []) + variants
    db.commit()

    total = len(seq.variants)
    return {"ok": True, "variants_count": len(variants), "total_variants": total, "variants": seq.variants}


@router.get("/device/sync")
def device_sync(
    db: Session = Depends(get_db),
    device_id: Optional[str] = Depends(verify_device_secret),
):
    """设备端同步 DM 序列模板 — 按设备所属用户过滤，NULL=共享模板"""
    sequences = get_device_visible_dm_sequences(db, device_id)
    return {"dm_sequences": [_to_device_dict(s) for s in sequences]}
