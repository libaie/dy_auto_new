"""AI Model Config Center — CRUD with encrypted api_key storage."""
import logging
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import httpx
from app.database import get_db
from app.deps import verify_admin_token, require_role
from app.db_models import AIModel
from app.services.crypto import encrypt, decrypt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai-models", tags=["ai-models"])


class ModelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    model_type: Literal["llm", "image", "video", "tts", "audit"]
    provider: str = Field(..., min_length=1, max_length=30)
    base_url: str = ""
    api_key: str = ""
    api_secret: str = ""
    model_name: str = Field(default="", max_length=100)
    config_json: dict | None = None


class ModelUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    model_name: str | None = None
    config_json: dict | None = None
    enabled: bool | None = None
    sort_order: int | None = None


def _model_dict(m: AIModel, reveal: bool = False) -> dict:
    ak = ""; asc = ""
    if reveal:
        if m.api_key:
            try: ak = decrypt(m.api_key)
            except Exception:
                logger.warning("decrypt api_key failed for model %s", m.id)
        if m.api_secret:
            try: asc = decrypt(m.api_secret)
            except Exception:
                logger.warning("decrypt api_secret failed for model %s", m.id)
    return {
        "id": m.id, "name": m.name, "model_type": m.model_type,
        "provider": m.provider, "base_url": m.base_url or "",
        "api_key": ak or ("****" if m.api_key and reveal else ""),
        "api_secret": asc,
        "model_name": m.model_name or "",
        "config_json": m.config_json or {},
        "enabled": m.enabled, "sort_order": m.sort_order,
        "api_key_configured": bool(m.api_key) if reveal else False,
    }


# ==== CRUD ====

@router.get("")
def list_models(
    model_type: str | None = Query(None),
    enabled: bool | None = Query(None),
    db: Session = Depends(get_db),
    _ = Depends(verify_admin_token),
):
    q = db.query(AIModel)
    if model_type:
        q = q.filter(AIModel.model_type == model_type)
    if enabled is not None:
        q = q.filter(AIModel.enabled == enabled)
    models = q.order_by(AIModel.sort_order, AIModel.created_at).all()
    return {"ok": True, "models": [_model_dict(m) for m in models]}


@router.get("/options")
def get_options(model_type: str | None = Query(None), db: Session = Depends(get_db),
                _ = Depends(verify_admin_token)):
    q = db.query(AIModel).filter(AIModel.enabled == True)
    if model_type:
        q = q.filter(AIModel.model_type == model_type)
    models = q.order_by(AIModel.sort_order, AIModel.created_at).all()
    return {"ok": True, "options": [
        {"id": m.id, "name": m.name, "model_type": m.model_type, "provider": m.provider}
        for m in models
    ]}


@router.get("/{model_id}")
def get_model(model_id: str, db: Session = Depends(get_db),
              _ = Depends(require_role("admin"))):
    m = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    return {"ok": True, "model": _model_dict(m, reveal=True)}


@router.post("")
def create_model(body: ModelCreate, db: Session = Depends(get_db),
                 _ = Depends(require_role("admin"))):
    m = AIModel(
        name=body.name, model_type=body.model_type, provider=body.provider,
        base_url=body.base_url or None,
        api_key=encrypt(body.api_key) if body.api_key else None,
        api_secret=encrypt(body.api_secret) if body.api_secret else None,
        model_name=body.model_name or None,
        config_json=body.config_json or {},
    )
    db.add(m)
    try:
        db.commit(); db.refresh(m)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "同类型同 provider 同 model_name 的模型已存在")
    return {"ok": True, "model": _model_dict(m, reveal=True)}


@router.put("/{model_id}")
def update_model(model_id: str, body: ModelUpdate, db: Session = Depends(get_db),
                 _ = Depends(require_role("admin"))):
    m = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    updates = body.model_dump(exclude_unset=True)
    if "api_key" in updates:
        updates["api_key"] = encrypt(updates["api_key"]) if updates["api_key"] else None
    if "api_secret" in updates:
        updates["api_secret"] = encrypt(updates["api_secret"]) if updates["api_secret"] else None
    for k, v in updates.items():
        setattr(m, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "同类型同 provider 同 model_name 的模型已存在")
    return {"ok": True, "model": _model_dict(m, reveal=True)}


@router.delete("/{model_id}")
def delete_model(model_id: str, db: Session = Depends(get_db),
                 _ = Depends(require_role("admin"))):
    m = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    db.delete(m); db.commit()
    return {"ok": True}


# ==== Test connection ====

@router.post("/{model_id}/test")
def test_connection(model_id: str, db: Session = Depends(get_db),
                     _ = Depends(require_role("admin"))):
    m = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    if not m.base_url:
        return {"ok": False, "error": "未配置 Base URL"}
    ak = decrypt(m.api_key) if m.api_key else ""
    if not ak and m.provider not in ("edge-tts", "none", "custom"):
        return {"ok": False, "error": "未配置 API Key"}

    headers = {}
    if m.provider == "anthropic":
        headers["x-api-key"] = ak
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {ak}"

    test_url = m.base_url.rstrip("/") + "/models"
    if m.provider == "anthropic":
        test_url = m.base_url.rstrip("/").rsplit("/v1/messages", 1)[0] + "/v1/models"

    try:
        resp = httpx.get(test_url, headers=headers, timeout=httpx.Timeout(10, connect=5))
        if resp.is_success:
            return {"ok": True, "status_code": resp.status_code}
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except httpx.ConnectError:
        return {"ok": False, "error": "连接失败 — 检查 Base URL"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "连接超时"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ==== Seed ====

DEFAULT_MODELS = [
    {"name":"DeepSeek V3","model_type":"llm","provider":"deepseek","base_url":"https://api.deepseek.com/v1","model_name":"deepseek-chat","config_json":{"thinking_enabled":False,"thinking_budget":8192,"max_tokens":4096,"temperature":0.7}},
    {"name":"GPT-4o","model_type":"llm","provider":"openai","base_url":"https://api.openai.com/v1","model_name":"gpt-4o","config_json":{"thinking_enabled":False,"thinking_budget":8192,"max_tokens":4096,"temperature":0.7}},
    {"name":"Qwen Max","model_type":"llm","provider":"openai","base_url":"https://dashscope.aliyuncs.com/compatible-mode/v1","model_name":"qwen-max","config_json":{"thinking_enabled":False,"thinking_budget":8192,"max_tokens":4096,"temperature":0.7}},
    {"name":"Claude Opus","model_type":"llm","provider":"anthropic","base_url":"https://api.anthropic.com/v1/messages","model_name":"claude-opus-4-7","config_json":{"thinking_enabled":True,"thinking_budget":8192,"max_tokens":4096,"temperature":0.7}},
    {"name":"Seedance Image","model_type":"image","provider":"seedance","base_url":"https://ark.cn-beijing.volces.com/api/v3","model_name":"seedance-image","config_json":{"default_size":"1024x1024","default_quality":"hd"}},
    {"name":"DALL-E 3","model_type":"image","provider":"openai","base_url":"https://api.openai.com/v1","model_name":"dall-e-3","config_json":{"default_size":"1024x1024","default_quality":"hd"}},
    {"name":"FLUX","model_type":"image","provider":"comfyui","base_url":"","model_name":"flux","config_json":{"default_size":"1024x1024","default_quality":"hd"}},
    {"name":"Seedance 2.0","model_type":"video","provider":"seedance","base_url":"https://ark.cn-beijing.volces.com/api/v3","model_name":"doubao-seedance-2.0-260128","config_json":{"default_resolution":"720p","default_duration":5,"default_aspect_ratio":"9:16"}},
    {"name":"Kling 3.0","model_type":"video","provider":"kling","base_url":"","model_name":"kling-v1-6","config_json":{"default_resolution":"1080p","default_duration":5,"default_aspect_ratio":"9:16"}},
    {"name":"Wan 2.7","model_type":"video","provider":"wan","base_url":"","model_name":"wan-2.7","config_json":{"default_resolution":"1080p","default_duration":5,"default_aspect_ratio":"9:16"}},
    {"name":"Edge-TTS","model_type":"tts","provider":"edge-tts","base_url":"","model_name":"edge-tts","config_json":{"default_voice":"zh-CN-XiaoxiaoNeural","default_language":"zh-CN","default_speed":1.0}},
    {"name":"Index-TTS","model_type":"tts","provider":"index-tts","base_url":"","model_name":"index-tts","config_json":{"default_voice":"","default_language":"zh-CN","default_speed":1.0}},
    {"name":"Spark-TTS","model_type":"tts","provider":"spark-tts","base_url":"","model_name":"spark-tts","config_json":{"default_voice":"","default_language":"zh-CN","default_speed":1.0}},
    {"name":"GPT-4o Audit","model_type":"audit","provider":"openai","base_url":"https://api.openai.com/v1","model_name":"gpt-4o","config_json":{"audit_mode":"single"}},
    {"name":"Gemini Audit","model_type":"audit","provider":"gemini","base_url":"","model_name":"gemini-2.5-pro","config_json":{"audit_mode":"single"}},
    {"name":"Skip Audit","model_type":"audit","provider":"none","base_url":"","model_name":"","config_json":{"audit_mode":"skip"}},
]

def seed_ai_models(db: Session):
    """Seed default model configs. Idempotent."""
    for entry in DEFAULT_MODELS:
        exists = db.query(AIModel).filter(
            AIModel.model_type == entry["model_type"],
            AIModel.provider == entry["provider"],
            AIModel.model_name == entry["model_name"],
        ).first()
        if not exists:
            db.add(AIModel(**entry))
    db.commit()
