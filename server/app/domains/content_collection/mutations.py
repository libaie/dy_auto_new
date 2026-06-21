"""内容采集业务域模块。

内容采集业务域，负责采集数据、私信序列、内容生成和实时事件。本文件负责 mutations 相关业务规则、状态转换和外部系统边界。
"""

import json
import logging
import random
import re

from fastapi import HTTPException

from app.db.models.content_collection import DMSequence
from app.domains.content_collection.dm_sequence_visibility import get_device_visible_dm_sequences
from app.domains.content_collection.content_service import content_service


logger = logging.getLogger(__name__)


def create_template(db, request):
    return content_service.create_template(
        db,
        name=request.name,
        category=request.category,
        body=request.body,
        variables=request.variables,
    )


def list_templates(db, category=None, skip: int = 0, limit: int = 50):
    limit = min(limit, 100)
    templates, total = content_service.list_templates(db, category=category, skip=skip, limit=limit)
    return {"templates": templates, "total": total}


def get_template(db, template_id: str):
    return content_service.get_template(db, template_id)


def update_template(db, template_id: str, request):
    updates = request.model_dump(exclude_none=True)
    return content_service.update_template(db, template_id, **updates)


def delete_template(db, template_id: str):
    return content_service.delete_template(db, template_id)


def add_sensitive_word(db, request):
    return content_service.add_sensitive_word(db, request.word)


def list_sensitive_words(db, skip: int = 0, limit: int = 200):
    words, total = content_service.list_sensitive_words(db, skip=skip, limit=limit)
    return {"words": words, "total": total}


def delete_sensitive_word(db, word_id: str):
    return content_service.delete_sensitive_word(db, word_id)


def list_dm_sequences(db, user, industry=None):
    user_id, _ = user
    query = db.query(DMSequence).filter(
        (DMSequence.user_id == user_id) | (DMSequence.user_id == None)
    )
    if industry:
        query = query.filter(DMSequence.industry == industry)
    sequences = query.order_by(DMSequence.updated_at.desc()).all()
    return {"sequences": [_dm_sequence_to_dict(sequence) for sequence in sequences]}


def create_dm_sequence(db, user, body):
    sorted_messages = sorted(
        [
            {"order": index + 1, "content": message.content, "delay_ms": message.delay_ms}
            for index, message in enumerate(sorted(body.messages, key=lambda item: item.order))
        ],
        key=lambda item: item["order"],
    )
    user_id, _ = user
    sequence = DMSequence(
        name=body.name,
        messages=sorted_messages,
        industry=body.industry or None,
        user_id=user_id,
    )
    db.add(sequence)
    db.commit()
    db.refresh(sequence)
    return _dm_sequence_to_dict(sequence)


def get_dm_sequence(db, user, sequence_id: str):
    user_id, _ = user
    sequence = db.query(DMSequence).filter(
        DMSequence.id == sequence_id,
        (DMSequence.user_id == user_id) | (DMSequence.user_id == None),
    ).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="序列模板不存在")
    return _dm_sequence_to_dict(sequence)


def update_dm_sequence(db, user, sequence_id: str, body):
    user_id, _ = user
    sequence = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="序列模板不存在")
    if sequence.user_id and sequence.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权修改其他用户的序列模板")

    if body.name is not None:
        sequence.name = body.name
    if body.messages is not None:
        new_messages = [
            {"order": index + 1, "content": message.content, "delay_ms": message.delay_ms}
            for index, message in enumerate(sorted(body.messages, key=lambda item: item.order))
        ]
        if new_messages != sequence.messages:
            sequence.variants = None
        sequence.messages = new_messages
    if body.industry is not None:
        old_industry = sequence.industry
        sequence.industry = body.industry or None
        if body.industry != (old_industry or None):
            sequence.variants = None
    if body.variants is not None:
        sequence.variants = body.variants

    db.commit()
    db.refresh(sequence)
    return _dm_sequence_to_dict(sequence)


def delete_dm_sequence(db, user, sequence_id: str):
    user_id, _ = user
    sequence = db.query(DMSequence).filter(DMSequence.id == sequence_id).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="序列模板不存在")
    if sequence.user_id and sequence.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权删除其他用户的序列模板")
    db.delete(sequence)
    db.commit()
    return {"deleted": True, "id": sequence_id}


async def generate_dm_sequence_events(db, body):
    from app.domains.model_configuration.ai_generator import ai_generator as generator
    from app.domains.content_collection.industry_profile_service import load_profile

    profile = load_profile(body.industry)
    system_prompt = profile["system_prompt"]
    sensitive_words = "、".join(profile["sensitive_words"])
    extreme_words = "、".join(profile["extreme_words"])
    style_guide = profile["style_guide"]

    user_prompt = (
        f"你是一个专业的私信话术生成助手。\n\n"
        f"## 行业约束\n"
        f"- 行业: {profile['label']}\n"
        f"- 话术风格: {style_guide}\n"
        f"- 绝对禁用词(包含任一词即不合格): {sensitive_words}\n"
        f"- 极限词禁用: {extreme_words}\n\n"
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
            async for chunk in generator.generate_custom_stream(
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

            for message in messages:
                content = message.get("content", "")
                for word in profile["sensitive_words"]:
                    if word in content:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'生成内容含敏感词: {word}'})}\n\n"
                        return
                for word in profile["extreme_words"]:
                    if word in content:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'生成内容含极限词: {word}'})}\n\n"
                        return

            messages = _jitter_messages(messages)
            yield f"data: {json.dumps({'type': 'done', 'messages': messages})}\n\n"
        except json.JSONDecodeError:
            yield f"data: {json.dumps({'type': 'error', 'message': 'JSON 解析失败，请重试'})}\n\n"
        except Exception as exc:
            logger.error("DM sequence generation failed: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': f'生成失败: {str(exc)[:200]}'})}\n\n"

    return event_stream()


async def generate_dm_variants(db, seq_id: str, body):
    from app.domains.model_configuration.ai_generator import ai_generator as generator
    from app.domains.content_collection.industry_profile_service import load_profile

    sequence = db.query(DMSequence).filter(DMSequence.id == seq_id).first()
    if not sequence:
        raise HTTPException(404, "DM序列不存在")
    if not sequence.messages or len(sequence.messages) < 3:
        raise HTTPException(400, "DM序列至少需要3条消息才能生成变体")

    industry = getattr(sequence, "industry", "general") or "general"
    profile = load_profile(industry)
    original_msg1 = (
        sequence.messages[0].get("content", "")
        if isinstance(sequence.messages[0], dict)
        else ""
    )
    original_msg2 = sequence.messages[1]
    original_msg3 = (
        sequence.messages[2].get("content", "")
        if len(sequence.messages) > 2 and isinstance(sequence.messages[2], dict)
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
    for index in range(body.count):
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
            response = await generator.generate_custom(
                db, variant_system_prompt, variant_prompt, max_tokens=1024
            )
            result = _robust_parse_variant_json(response)
            if not result:
                logger.warning("Variant attempt %d JSON parse failed, skipping", index + 1)
                continue

            rewritten_msg1 = result.get("msg1", original_msg1)
            rewritten_msg3 = result.get("msg3", original_msg3)
            if _contains_blocked_word(rewritten_msg1, rewritten_msg3, profile):
                continue

            variant = [
                {
                    "order": 1,
                    "content": rewritten_msg1,
                    "delay_ms": sequence.messages[0].get("delay_ms", 2000),
                },
                original_msg2,
                {
                    "order": 3,
                    "content": rewritten_msg3,
                    "delay_ms": (
                        sequence.messages[2].get("delay_ms", 2000)
                        if len(sequence.messages) > 2
                        else 2000
                    ),
                },
            ]
            variants.append(_randomize_variant_delays(variant))
        except Exception as exc:
            logger.warning("Variant generation attempt %d failed: %s", index + 1, exc)
            continue

    if not variants:
        raise HTTPException(500, "无法生成合规变体，请调整原始话术后重试")

    sequence.variants = (sequence.variants or []) + variants
    db.commit()
    return {
        "ok": True,
        "variants_count": len(variants),
        "total_variants": len(sequence.variants),
        "variants": sequence.variants,
    }


def device_sync_dm_sequences(db, device_id):
    sequences = get_device_visible_dm_sequences(db, device_id)
    return {"dm_sequences": [_dm_sequence_to_device_dict(sequence) for sequence in sequences]}


def _dm_sequence_to_dict(sequence: DMSequence) -> dict:
    return {
        "id": sequence.id,
        "name": sequence.name,
        "messages": sequence.messages,
        "message_count": len(sequence.messages),
        "industry": sequence.industry or "",
        "variants_count": len(sequence.variants) if sequence.variants else 0,
        "variants": sequence.variants,
        "created_at": str(sequence.created_at) if sequence.created_at else None,
        "updated_at": str(sequence.updated_at) if sequence.updated_at else None,
    }


def _dm_sequence_to_device_dict(sequence: DMSequence) -> dict:
    messages = _jitter_messages(sequence.messages) if sequence.messages else None
    variants = _randomize_variants(sequence.variants) if sequence.variants else None
    return {"id": sequence.id, "messages": messages, "variants": variants}


def _jitter(delay_ms: int) -> int:
    if delay_ms <= 0:
        return delay_ms
    delta = int(delay_ms * 0.25)
    return max(0, delay_ms + random.randint(-delta, delta))


def _jitter_messages(messages: list[dict]) -> list[dict]:
    return [
        {**message, "delay_ms": _jitter(message.get("delay_ms", 0))}
        for message in messages
    ]


def _variant_delay_ms() -> int:
    return random.randint(1500, 3000)


def _randomize_variant_delays(variant: list[dict]) -> list[dict]:
    return [{**message, "delay_ms": _variant_delay_ms()} for message in variant]


def _randomize_variants(variants: list[list[dict]]) -> list[list[dict]]:
    return [_randomize_variant_delays(variant) for variant in variants]


def _robust_parse_variant_json(raw: str) -> dict | None:
    if not raw:
        return None
    clean = raw.strip()
    fence_match = re.match(r"```(?:\w+)?\s*\n?(.*?)```", clean, re.DOTALL)
    if fence_match:
        clean = fence_match.group(1).strip()
    elif clean.startswith("```"):
        lines = clean.split("\n")
        if len(lines) > 1:
            clean = "\n".join(lines[1:])
        if clean.endswith("```"):
            clean = clean[:clean.rfind("```")].strip()

    match = re.search(r"\{[\s\S]*\}", clean)
    if not match:
        return None
    candidate = match.group()
    key_fixes = [
        ("msg_1", "msg1"), ("msg_3", "msg3"),
        ("message1", "msg1"), ("message3", "msg3"),
        ("message_1", "msg1"), ("message_3", "msg3"),
        ("hook", "msg1"), ("cta", "msg3"),
    ]

    result = None
    try:
        result = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        pass
    if result is None:
        fixed = candidate
        for wrong, right in key_fixes:
            fixed = fixed.replace(f'"{wrong}"', f'"{right}"')
        try:
            result = json.loads(fixed)
        except (json.JSONDecodeError, TypeError):
            return None

    for wrong, right in key_fixes:
        if wrong in result:
            result[right] = result.pop(wrong)
    if not result or ("msg1" not in result and "msg3" not in result):
        return None
    return result


def _normalize_generated_sequence_messages(messages: list) -> list[dict]:
    normalized = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError("AI 返回的消息格式异常")
        content = (
            message.get("content")
            or message.get("message")
            or message.get("text")
            or message.get("msg")
        )
        if not isinstance(content, str) or not content.strip():
            raise ValueError("AI 返回的消息缺少内容字段")
        normalized.append({
            "order": int(message.get("order") or index + 1),
            "content": content.strip(),
            "delay_ms": int(message.get("delay_ms") or message.get("delayMs") or 0),
        })
    return normalized


def _contains_blocked_word(message1: str, message3: str, profile: dict) -> bool:
    for word in profile["sensitive_words"]:
        if word in message1 or word in message3:
            return True
    for word in profile["extreme_words"]:
        if word in message1 or word in message3:
            return True
    return False
