"""Prompt template management CRUD API — admin only."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from typing import Any, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_ai_config_with_key
from app.database import get_db, SessionLocal
from app.deps import verify_admin_token, require_role
from app.services.ai_generator import ai_generator as gen
from app.domains.prompt_management.prompt_template_service import prompt_template_service

logger = logging.getLogger("app.routers.prompt_templates")

router = APIRouter(prefix="/api/prompt-templates", tags=["prompt-templates"])


class TemplateGenerateRequest(BaseModel):
    description: str
    industry: str = "health"


class TemplateRewriteRequest(BaseModel):
    content: Any = None
    instruction: Any = None
    industry: str = "health"


class TemplateCreateRequest(BaseModel):
    name: str
    industry: str = "health"
    description: str = ""
    content: dict


class TemplateUpdateRequest(BaseModel):
    content: Optional[dict] = None
    industry: Optional[str] = None
    description: Optional[str] = None


class TemplateToggleRequest(BaseModel):
    enabled: bool


TEMPLATE_SCHEMA_DESC = """提示词模板 JSON 结构：
{
  "identity": { "role": "角色描述", "constraints": ["约束1", "约束2"] },
  "disabledWords": "禁用词列表，用 / 分隔",
  "semanticGuide": {
    "mission": "语义分析的核心问题",
    "highValueSignals": ["高价值信号1：描述 → 含义"],
    "lowValueSignals": ["低价值信号1：描述 → 含义"],
    "keyExamples": ["示例: 具体评论 → 信号分析 → 结论"]
  },
  "analysis": {
    "intents": ["intent_type: 描述和示例"],
    "sentiments": ["sentiment_type: 描述"],
    "scoringRules": ["评分规则"],
    "replyRules": ["回复生成规则"],
    "replyExample": { "good": "好的回复示例（纯回复正文，不含原文引用）", "bad": "不好的回复示例（纯回复正文，不含原文引用）" },
    "tiers": { "tier_name": "对应语气描述" }
  },
  "videoComment": {
    "context": "场景上下文",
    "goal": "评论的目标",
    "rules": ["规则1", "规则2"]
  },
  "dmOpener": {
    "context": "破冰上下文",
    "identity": ["身份设定"],
    "goal": "破冰目标",
    "style": ["风格规则"],
    "tierTones": { "tier_name": "语气描述" }
  },
  "dmStages": {
    "qualifying": { "name": "了解需求", "goal": "阶段目标", "style": "风格", "maxTokens": 150 },
    "nurturing": { "name": "信任培育", "goal": "...", "style": "...", "maxTokens": 200 },
    "converting": { "name": "转化引导", "goal": "...", "style": "...", "maxTokens": 150 },
    "follow_up": { "name": "唤回", "goal": "...", "style": "...", "maxTokens": 120 }
  },
  "localFilter": { "exclude": ["排除关键词"], "include": ["包含关键词"] }
}"""

TEMPLATE_GEN_SYSTEM = """你是一个 AI 提示词模板生成专家。根据用户描述，生成完整的提示词模板 JSON。

## 输出要求
1. 严格按指定的 JSON 结构输出
2. 所有字段必填，数组至少包含 3 个元素
3. 提示词内容具体、可执行，不要泛泛而谈
4. highValueSignals 要覆盖常见的需求表达模式
5. keyExamples 要给出正反面对比例子
6. scoringRules 要有明确分值
7. replyRules 要有具体指导，不要只说"自然一点"
8. 直接输出 JSON，不要 markdown 代码块包裹，不要解释
9. **replyExample.good 和 replyExample.bad 只写回复正文，绝对不要包含「评论'xxx' → 回复：'yyy'」这种元格式**

## 场景说明
- 场景1 (videoComment): 视频评论 = 在视频下留言吸引其他观众注意，相当于广告位
- 场景2 (analysis): 评论回复 = 分析已有评论并生成回复，吸引评论者注意
- 场景3 (dmOpener + dmStages): 私信转化 = 多阶段私信漏斗

## replyExample 正确 vs 错误示例
❌ 错误: { "good": "评论'价格多少' → 回复：'私信您了解详情哦'", "bad": "评论'太贵了' → 回复：'一分钱一分货'" }
✅ 正确: { "good": "私信您了解详情哦～不同方案价格不同，看看哪个适合您", "bad": "亲可以看看哦" }
replyExample 中的文本就是最终输出的回复内容，不需要标注原文是什么、回复是什么。"""


TEMPLATE_REWRITE_SYSTEM = """You are an AI prompt template rewrite assistant.

Return only the complete rewritten prompt template JSON object. Preserve the
existing schema and required fields, apply only the user's rewrite instruction,
and keep unrelated fields stable where possible. Do not include markdown fences
or explanatory text."""


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _strip_json_fence(raw: str) -> str:
    content = raw.strip()
    if not content.startswith("```"):
        return content

    lines = content.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _canonical_template_json(content: dict) -> str:
    return json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@router.post("/generate")
async def generate_template(
    request: TemplateGenerateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """AI 根据描述生成提示词模板 JSON"""
    from app.services.ai_generator import ai_generator as gen

    user_prompt = (
        f"行业：{request.industry}\n"
        f"用户描述：{request.description}\n\n"
        f"参考 JSON 结构：\n{TEMPLATE_SCHEMA_DESC}\n\n"
        f"请根据用户描述和行业，生成完整的提示词模板 JSON。"
        f"行业特定的语义信号、禁用词、示例都要与行业匹配。"
    )

    try:
        raw = await gen.generate_custom(db, TEMPLATE_GEN_SYSTEM, user_prompt, max_tokens=4096)
        content = raw.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:]) if lines[0].startswith("```") else content
            if content.endswith("```"):
                content = content[: content.rfind("```")].strip()
        template = json.loads(content)
        # 校验 AI 生成的 replyExample 格式
        try:
            prompt_template_service._validate_reply_example(template)
        except ValueError as ve:
            raise HTTPException(status_code=422, detail=f"AI 生成的 replyExample 格式不正确: {str(ve)}")
        return {"content": template}
    except json.JSONDecodeError as e:
        logger.warning("AI generated invalid JSON: %s", str(e)[:200])
        raise HTTPException(status_code=500, detail=f"AI 生成的 JSON 格式无效: {str(e)[:200]}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Template generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.post("/generate-stream")
async def generate_template_stream(
    request: TemplateGenerateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """AI 根据描述生成提示词模板 JSON（SSE 流式输出，避免超时）"""
    from app.services.ai_generator import ai_generator as gen

    user_prompt = (
        f"行业：{request.industry}\n"
        f"用户描述：{request.description}\n\n"
        f"参考 JSON 结构：\n{TEMPLATE_SCHEMA_DESC}\n\n"
        f"请根据用户描述和行业，生成完整的提示词模板 JSON。"
        f"行业特定的语义信号、禁用词、示例都要与行业匹配。"
    )

    async def event_stream():
        yield f"data: {json.dumps({'type': 'status', 'text': '正在调用 AI 生成...'})}\n\n"

        raw_chunks = []
        try:
            async for chunk in gen.generate_custom_stream(
                db, TEMPLATE_GEN_SYSTEM, user_prompt, max_tokens=4096
            ):
                raw_chunks.append(chunk)
                # Forward each token to the client
                yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"

            # All tokens received, assemble and parse
            raw = "".join(raw_chunks).strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:])
                if raw.endswith("```"):
                    raw = raw[: raw.rfind("```")].strip()
            template = json.loads(raw)
            # 校验 AI 生成的 replyExample 格式
            try:
                prompt_template_service._validate_reply_example(template)
            except ValueError as ve:
                yield f"data: {json.dumps({'type': 'warning', 'message': f'replyExample 格式不正确: {str(ve)}。请重新生成。', 'content': template})}\n\n"
                return
            yield f"data: {json.dumps({'type': 'done', 'content': template})}\n\n"
        except json.JSONDecodeError as e:
            logger.warning("AI generated invalid JSON: %s", str(e)[:200])
            yield f"data: {json.dumps({'type': 'error', 'message': f'AI 生成的 JSON 格式无效: {str(e)[:200]}'})}\n\n"
        except Exception as e:
            logger.error("Template generation failed: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)[:200]})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/rewrite-stream")
async def rewrite_template_stream(
    request: TemplateRewriteRequest,
    user = Depends(require_role("admin")),
):
    """AI rewrite preview for prompt template JSON. Stateless SSE endpoint."""
    def stream_headers():
        return {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }

    def error_stream(message: str):
        async def stream():
            yield _sse({"type": "error", "message": message})

        return stream()

    logger.info("Prompt template rewrite started industry=%s", request.industry)

    try:
        instruction = prompt_template_service.validate_rewrite_request(
            request.content,
            request.instruction,
        )
        user_prompt = prompt_template_service.build_rewrite_prompt(
            request.industry,
            request.content,
            instruction,
        )
        with SessionLocal() as db:
            ai_cfg = get_ai_config_with_key(db)
        if not ai_cfg:
            raise ValueError("AI API not configured")
    except ValueError as e:
        logger.warning(
            "Prompt template rewrite failed industry=%s error_type=preflight",
            request.industry,
        )
        return StreamingResponse(
            error_stream(str(e)[:200]),
            media_type="text/event-stream",
            headers=stream_headers(),
        )

    async def event_stream():
        raw_chunks = []
        try:
            yield _sse({"type": "status", "text": "Rewriting prompt template..."})
            async for chunk in gen.generate_custom_stream_with_config(
                ai_cfg,
                TEMPLATE_REWRITE_SYSTEM,
                user_prompt,
                max_tokens=4096,
            ):
                raw_chunks.append(chunk)
                yield _sse({"type": "token", "text": chunk})

            raw = _strip_json_fence("".join(raw_chunks))
            rewritten = json.loads(raw)
            prompt_template_service.validate_rewrite_output(rewritten)
            if _canonical_template_json(rewritten) == _canonical_template_json(request.content):
                raise ValueError(
                    "AI rewrite returned unchanged content; make the instruction more specific"
                )
            logger.info("Prompt template rewrite succeeded industry=%s", request.industry)
            yield _sse({"type": "done", "content": rewritten})
        except json.JSONDecodeError as e:
            logger.warning(
                "Prompt template rewrite failed industry=%s error_type=json exception_type=%s",
                request.industry,
                type(e).__name__,
            )
            yield _sse({"type": "error", "message": f"AI generated invalid JSON: {str(e)[:200]}"})
        except ValueError as e:
            logger.warning(
                "Prompt template rewrite failed industry=%s error_type=validation",
                request.industry,
            )
            yield _sse({"type": "error", "message": str(e)[:200]})
        except Exception as e:
            logger.error(
                "Prompt template rewrite failed industry=%s error_type=unexpected exception_type=%s",
                request.industry,
                type(e).__name__,
            )
            yield _sse({"type": "error", "message": str(e)[:200]})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=stream_headers(),
    )


@router.get("")
def list_templates(
    include_disabled: bool = Query(False),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    templates = prompt_template_service.list_all_templates(db, include_disabled=include_disabled)
    version = prompt_template_service.get_version(db)
    return {"templates": templates, "total": len(templates), "version": version}


@router.get("/{name}")
def get_template(
    name: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    tmpl = prompt_template_service.get_template(db, name)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tmpl


@router.post("")
async def create_template(
    request: TemplateCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    try:
        tmpl = prompt_template_service.create_template(
            db, name=request.name, industry=request.industry,
            content=request.content, description=request.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    version = prompt_template_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "prompt_templates_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({
        "event": "prompt_templates_changed",
        "version": version,
    })
    return tmpl


@router.put("/{name}")
async def update_template(
    name: str,
    request: TemplateUpdateRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    try:
        tmpl = prompt_template_service.update_template(
            db, name=name,
            content=request.content,
            industry=request.industry,
            description=request.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    version = prompt_template_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "prompt_templates_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({
        "event": "prompt_templates_changed",
        "version": version,
    })
    return tmpl


@router.delete("/{name}")
async def delete_template(
    name: str,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    deleted = prompt_template_service.delete_template(db, name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")

    version = prompt_template_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "prompt_templates_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({
        "event": "prompt_templates_changed",
        "version": version,
    })
    return {"deleted": True, "name": name}


@router.patch("/{name}/toggle")
async def toggle_template(
    name: str,
    request: TemplateToggleRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    try:
        tmpl = prompt_template_service.toggle_template(db, name, request.enabled)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    version = prompt_template_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "prompt_templates_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({
        "event": "prompt_templates_changed",
        "version": version,
    })
    return tmpl
