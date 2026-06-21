"""AI 审图 API — 使用 AIModel 配置进行多模态审计."""
import logging
import json as _json
import re
import httpx
from langchain_core.tools import tool
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db.models.model_configuration import AIModel
from app.db.models.quality_audit import AuditReport
from app.domains.quality_audit.audit_gate import classify_audit_gate
from app.domains.model_configuration.ai_generator import AiGeneratorService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditImageRequest(BaseModel):
    image_url: str
    target_type: str = "frame"
    target_id: str = ""
    audit_model_id: str | None = None
    audit_criteria: list[str] | None = None


def _get_audit_model(db: Session, model_id: str | None) -> dict:
    """Resolve audit model via registry with backward-compatible fallback."""
    from app.domains.model_configuration.model_registry import get_model_for_scene, ModelResolutionError
    try:
        return get_model_for_scene(db, "quality_audit", explicit_model_id=model_id)
    except ModelResolutionError:
        return {}


def _do_audit(model: dict, image_url: str, criteria: list[str] | None) -> dict:
    provider = model.get("provider", "")
    if provider == "none":
        return {"score": 1.0, "pass_fail": True, "issues": [], "raw": "skipped"}
    if not model.get("api_key"):
        return {"score": 1.0, "pass_fail": True, "issues": ["审计模型未配置 API Key"], "raw": ""}

    criteria_text = "\n".join(f"- {c}" for c in (criteria or [
        "画面质量：无模糊、无噪点、分辨率达标",
        "构图合理性：主体清晰、画面平衡",
        "内容安全：无不适宜内容、无违规元素",
        "色彩和谐：无过度曝光、无色彩失真",
    ]))

    system_prompt = (
        "你是专业的视频画面质量审计专家。根据审计标准评分。"
        "返回 JSON：{\"score\": 0.0-1.0, \"pass\": true/false, \"issues\": [\"问题\"]}。只返回 JSON。"
    )

    if provider == "gemini":
        return _audit_gemini(model, image_url, criteria_text, system_prompt)
    return _audit_openai_compatible(model, image_url, criteria_text, system_prompt)


def _audit_config(model: dict) -> dict:
    config = {}
    for key in ("config_json", "config"):
        value = model.get(key)
        if isinstance(value, dict):
            config.update(value)
    return config


def _audit_model_name(model: dict) -> str:
    return str(model.get("model_name") or model.get("model") or "gpt-4o")


def _supports_vision_audit(model: dict, config: dict) -> bool:
    if "supports_vision_audit" in config:
        return bool(config["supports_vision_audit"])
    provider = str(model.get("provider") or "").lower()
    model_name = _audit_model_name(model).lower()
    return provider == "openai" and (model_name.startswith("gpt-4o") or "vision" in model_name)


def _audit_user_content(image_url: str, criteria_text: str, *, supports_vision: bool):
    if supports_vision:
        return [
            {"type": "text", "text": f"审计标准：\n{criteria_text}\n\n请审计这张图片。"},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    return (
        f"审计标准：\n{criteria_text}\n\n"
        f"资产地址或本地路径：{image_url}\n\n"
        "请基于资产可访问性、格式、生成链路元信息和审计标准进行保守质量审计；"
        "如果无法直接查看画面，请在 issues 中说明限制。"
    )


def _audit_openai_compatible(model: dict, image_url: str, criteria_text: str, system_prompt: str) -> dict:
    config = _audit_config(model)
    generator = AiGeneratorService()
    chat_model = generator._create_chat_model(
        {
            "base_url": model.get("base_url", "https://api.openai.com/v1"),
            "api_key": model["api_key"],
            "model": _audit_model_name(model),
            "timeout": 60,
        },
        max_tokens=int(config.get("max_tokens", 500)),
        temperature=float(config.get("temperature", 0.1)),
    )
    response = chat_model.invoke([
        ("system", system_prompt),
        (
            "human",
            _audit_user_content(
                image_url,
                criteria_text,
                supports_vision=_supports_vision_audit(model, config),
            ),
        ),
    ])
    return _parse_audit_json(generator._message_text(response))

@tool
def gemini_audit_request(model_name: str, api_key: str, image_url: str, criteria_text: str, system_prompt: str) -> dict:
    """Submit one Gemini quality-audit request and return the raw model text."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    resp = httpx.post(
        url,
        json={
            "contents": [{"parts": [
                {"text": f"{system_prompt}\n\n审计标准：\n{criteria_text}"},
                {"inline_data": {"mime_type": "image/jpeg", "data": image_url}},
            ]}],
            "generationConfig": {"maxOutputTokens": 500, "temperature": 0.1},
        },
        timeout=httpx.Timeout(60, connect=10),
    )
    resp.raise_for_status()
    data = resp.json()
    return {"raw": data["candidates"][0]["content"]["parts"][0]["text"]}


def _audit_gemini(model: dict, image_url: str, criteria_text: str, system_prompt: str) -> dict:
    result = gemini_audit_request.invoke({
        "model_name": model["model_name"],
        "api_key": model["api_key"],
        "image_url": image_url,
        "criteria_text": criteria_text,
        "system_prompt": system_prompt,
    })
    return _parse_audit_json(result["raw"])


def _parse_audit_json(raw: str) -> dict:
    m = re.search(r'\{[\s\S]*\}', raw)
    if m:
        try:
            p = _json.loads(m.group(0))
            return {
                "score": float(p.get("score", 0.5)),
                "pass_fail": bool(p.get("pass", True)),
                "issues": p.get("issues", []),
                "raw": raw[:200],
            }
        except Exception:
            pass
    return {"score": 0.5, "pass_fail": True, "issues": [], "raw": raw[:200]}


@router.post("/image")
def audit_image(
    body: AuditImageRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    model_config = _get_audit_model(db, body.audit_model_id)
    try:
        result = _do_audit(model_config, body.image_url, body.audit_criteria)
        result = classify_audit_gate(result)
    except Exception as e:
        logger.exception("Audit API call failed")
        result = classify_audit_gate(
            {"score": 0.0, "pass_fail": False, "issues": [str(e)], "raw": ""},
            error=True,
        )

    report = AuditReport(
        target_type=body.target_type,
        target_id=body.target_id,
        image_url=body.image_url,
        auditor_model=f"{model_config.get('provider', 'unknown')}:{model_config.get('model_name', 'unknown')}",
        score=result["score"],
        pass_fail=result["pass_fail"],
        issues_json=result.get("issues", []),
        raw_response=result.get("raw", ""),
    )
    db.add(report); db.commit(); db.refresh(report)
    return {"ok": True, "report": {
        "id": report.id, "score": report.score, "pass_fail": report.pass_fail,
        "issues": report.issues_json, "auditor_model": report.auditor_model,
        "gate_status": result["gate_status"],
    }}


@router.get("/reports/{target_type}/{target_id}")
def list_reports(target_type: str, target_id: str,
                 db: Session = Depends(get_db)):
    reports = db.query(AuditReport).filter(
        AuditReport.target_type == target_type,
        AuditReport.target_id == target_id,
    ).order_by(AuditReport.created_at.desc()).all()
    return {"ok": True, "reports": [
        {col.name: getattr(r, col.name) for col in AuditReport.__table__.columns}
        for r in reports
    ]}
