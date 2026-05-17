"""AI 审图 API — 使用 AIModel 配置直接调用 GPT-4o/Gemini Vision 进行多模态审计."""
import logging
import json as _json
import re
import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import AuditReport, AIModel
from app.services.crypto import decrypt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditImageRequest(BaseModel):
    image_url: str
    target_type: str = "frame"
    target_id: str = ""
    audit_model_id: str | None = None
    audit_criteria: list[str] | None = None


def _get_audit_model(db: Session, model_id: str | None) -> dict:
    if model_id:
        m = db.query(AIModel).filter(AIModel.id == model_id).first()
    else:
        m = db.query(AIModel).filter(
            AIModel.model_type == "audit", AIModel.enabled == True
        ).order_by(AIModel.sort_order).first()
    if not m:
        return {}
    ak = ""
    if m.api_key:
        try: ak = decrypt(m.api_key)
        except Exception: logger.warning("decrypt api_key failed for audit model %s", m.id)
    return {
        "id": m.id, "name": m.name, "provider": m.provider,
        "base_url": m.base_url or "", "api_key": ak,
        "model_name": m.model_name or "",
        "config_json": m.config_json or {},
    }


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


def _audit_openai_compatible(model: dict, image_url: str, criteria_text: str, system_prompt: str) -> dict:
    base = model.get("base_url", "https://api.openai.com/v1")
    resp = httpx.post(
        f"{base.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {model['api_key']}"},
        json={
            "model": model.get("model_name", "gpt-4o"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": f"审计标准：\n{criteria_text}\n\n请审计这张图片。"},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]},
            ],
            "max_tokens": 500, "temperature": 0.1,
        },
        timeout=httpx.Timeout(60, connect=10),
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    return _parse_audit_json(raw)


def _audit_gemini(model: dict, image_url: str, criteria_text: str, system_prompt: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model['model_name']}:generateContent?key={model['api_key']}"
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
    raw = data["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_audit_json(raw)


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
    except Exception as e:
        logger.exception("Audit API call failed")
        result = {"score": 0.0, "pass_fail": False, "issues": [str(e)], "raw": ""}

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
