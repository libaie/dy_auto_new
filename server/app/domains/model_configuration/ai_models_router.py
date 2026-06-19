"""AI Model Config Center — CRUD with encrypted api_key storage."""
import ipaddress
import logging
from typing import Literal
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import httpx
from app.database import get_db
from app.deps import verify_admin_token, require_role
from app.db_models import AIModel
from app.services.crypto import encrypt, decrypt
from app.services.model_schema import get_schema_payload, get_provider_preset
from app.data.model_schema_data import scene_key_to_model_type

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai-models", tags=["ai-models"])

SEEDANCE_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3"
SEEDREAM_IMAGE_MODEL = "doubao-seedream-5.0-lite"
SEEDANCE_VIDEO_MODEL = "doubao-seedance-2.0"
BAILIAN_COMPATIBLE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
BAILIAN_QWEN_37_PLUS_MODEL = "qwen3.7-plus"
BAILIAN_EXPERT_REVIEW_MODEL = BAILIAN_QWEN_37_PLUS_MODEL
PIXELLE_COMPOSE_MODEL = "pixelle-compose-local"
LEGACY_SEEDANCE_ARK_BASE_URL = "https://ark.cn-beijing.volces.com" + "/api/v3"
LEGACY_SEEDANCE_MODEL_NAMES = {
    "image": ("seedance-image", "doubao-seedance-image"),
    "video": ("doubao-seedance-2.0-260128", "doubao-seedance-2-0-260128"),
}
LEGACY_EXPERT_REVIEW_DEFAULT_NAME = "OpenAI Compatible Expert Review"


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
    model_type: Literal["llm", "image", "video", "tts", "audit"] | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    model_name: str | None = None
    config_json: dict | None = None
    enabled: bool | None = None
    sort_order: int | None = None
    clear_secret: bool = False


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
    scene_key: str | None = Query(None),
    enabled: bool | None = Query(None),
    db: Session = Depends(get_db),
    _ = Depends(verify_admin_token),
):
    q = db.query(AIModel)
    if scene_key:
        try:
            model_type = scene_key_to_model_type(scene_key)
        except ValueError:
            return {"ok": True, "models": []}
    if model_type:
        q = q.filter(AIModel.model_type == model_type)
    if enabled is not None:
        q = q.filter(AIModel.enabled == enabled)
    models = q.order_by(AIModel.sort_order, AIModel.created_at).all()
    return {"ok": True, "models": [_model_dict(m) for m in models]}


@router.get("/options")
def get_options(
    model_type: str | None = Query(None),
    scene_key: str | None = Query(None),
    db: Session = Depends(get_db),
    _ = Depends(verify_admin_token),
):
    q = db.query(AIModel).filter(AIModel.enabled == True)
    if scene_key:
        try:
            model_type = scene_key_to_model_type(scene_key)
        except ValueError:
            return {"ok": True, "options": []}
    if model_type:
        q = q.filter(AIModel.model_type == model_type)
    models = q.order_by(AIModel.sort_order, AIModel.created_at).all()
    return {"ok": True, "options": [
        {"id": m.id, "name": m.name, "model_type": m.model_type, "provider": m.provider}
        for m in models
    ]}


@router.get("/schema")
def get_schema(_ = Depends(verify_admin_token)):
    """Return scene definitions, provider presets, protocols, and custom field policy."""
    return {"ok": True, **get_schema_payload()}


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
    # Preserve secrets: blank values keep existing; clear_secret flag wipes
    if body.clear_secret:
        if "api_key" not in updates:
            updates["api_key"] = None
        if "api_secret" not in updates:
            updates["api_secret"] = None
    else:
        if "api_key" in updates and not updates["api_key"]:
            del updates["api_key"]
        if "api_secret" in updates and not updates["api_secret"]:
            del updates["api_secret"]
    if "api_key" in updates:
        updates["api_key"] = encrypt(updates["api_key"]) if updates["api_key"] else None
    if "api_secret" in updates:
        updates["api_secret"] = encrypt(updates["api_secret"]) if updates["api_secret"] else None
    for k, v in updates.items():
        if k == "clear_secret":
            continue
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


# ==== SSRF guard ====

_SSRF_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_url(url: str) -> bool:
    """Check if a URL targets a private/internal IP address (SSRF prevention)."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return True
        if host.lower() in {"localhost", "localhost.localdomain"} or host.lower().endswith(".localhost"):
            return True
        try:
            addr = ipaddress.ip_address(host)
        except ValueError:
            return False
        for net in _SSRF_BLOCKED_NETWORKS:
            if addr in net:
                return True
        return False
    except ValueError:
        return True


def _build_auth_headers(provider: str, api_key: str) -> dict:
    """Build auth headers based on provider protocol."""
    if provider == "anthropic":
        return {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    return {"Authorization": f"Bearer {api_key}"}


# ==== Test connection ====

@router.post("/{model_id}/test")
def test_connection(model_id: str, db: Session = Depends(get_db),
                     _ = Depends(require_role("admin"))):
    m = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    if not m.base_url:
        return {"ok": False, "error": "未配置 Base URL"}

    preset = get_provider_preset(m.provider)
    strategy = preset.get("test_strategy", "list_models")

    if strategy == "noop":
        return {"ok": False, "error": "此提供商不支持自动连接测试"}

    # SSRF guard
    if _is_private_url(m.base_url):
        return {"ok": False, "error": "不允许连接内网地址"}

    ak = decrypt(m.api_key) if m.api_key else ""
    if not ak and m.provider not in ("edge-tts", "custom"):
        return {"ok": False, "error": "未配置 API Key"}

    headers = _build_auth_headers(m.provider, ak)

    if strategy == "list_models":
        if m.provider == "anthropic":
            test_url = m.base_url.rstrip("/")
            if not test_url.endswith("/v1/models"):
                base = test_url.rsplit("/v1/messages", 1)[0]
                test_url = base + "/v1/models"
        else:
            test_url = m.base_url.rstrip("/") + "/models"
    elif strategy == "health_check":
        test_path = preset.get("test_path", "/")
        test_url = m.base_url.rstrip("/") + test_path
    else:
        test_url = m.base_url.rstrip("/") + "/models"

    try:
        resp = httpx.get(test_url, headers=headers, timeout=httpx.Timeout(10, connect=5))
        if resp.is_success:
            return {"ok": True, "status_code": resp.status_code, "strategy": strategy}
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "strategy": strategy}
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
    {"name":"Bailian Qwen 3.7 Plus","model_type":"llm","provider":"bailian","base_url":BAILIAN_COMPATIBLE_BASE_URL,"model_name":BAILIAN_QWEN_37_PLUS_MODEL,"sort_order":-100,"config_json":{"scene_key":"llm_agency_expert_review","scene_keys":["script_generation","llm_agency_expert_review"],"protocol":"openai_chat_completions","thinking_enabled":False,"thinking_budget":8192,"max_tokens":8192,"temperature":0.2}},
    {"name":"Qwen Max","model_type":"llm","provider":"openai","base_url":"https://dashscope.aliyuncs.com/compatible-mode/v1","model_name":"qwen-max","config_json":{"thinking_enabled":False,"thinking_budget":8192,"max_tokens":4096,"temperature":0.7}},
    {"name":"Claude Opus","model_type":"llm","provider":"anthropic","base_url":"https://api.anthropic.com/v1/messages","model_name":"claude-opus-4-7","config_json":{"thinking_enabled":True,"thinking_budget":8192,"max_tokens":4096,"temperature":0.7}},
    {"name":"Seedream 5.0 Lite","model_type":"image","provider":"seedance","base_url":SEEDANCE_ARK_BASE_URL,"model_name":SEEDREAM_IMAGE_MODEL,"config_json":{"scene_key":"image_generation","scene_keys":["image_generation","image_editing"],"default_size":"3K","default_quality":"hd","capabilities":{"text_to_image":True,"image_to_image":True,"multi_reference_to_image":True,"text_to_image_set":True,"image_to_image_set":True,"multi_reference_to_image_set":True},"limits":{"min_reference_images":1,"max_reference_images":14,"max_output_images":15,"max_reference_plus_output_images":15,"max_input_image_mb":30,"max_input_pixels":36000000,"aspect_ratio_range":[0.0625,16]},"provider_options_schema":{"sequential_image_generation":{"type":"select","options":["disabled","auto"]},"max_images":{"type":"number","min":1,"max":15},"stream":{"type":"boolean"},"response_format":{"type":"select","options":["url","b64_json"]},"output_format":{"type":"select","options":["jpeg","png"]},"watermark":{"type":"boolean"},"optimize_prompt_mode":{"type":"select","options":["standard","fast"]},"web_search":{"type":"boolean"}}}},
    {"name":"Qwen Image 2.0 Pro","model_type":"image","provider":"qwen-image","base_url":"https://dashscope.aliyuncs.com/api/v1","model_name":"qwen-image-2.0-pro","config_json":{"scene_key":"image_generation","scene_keys":["image_generation","image_editing"],"default_size":"1536*2688","default_quality":"standard","protocol":"dashscope_multimodal_generation","task_path":"/services/aigc/multimodal-generation/generation","capabilities":{"text_to_image":True,"image_to_image":False,"multi_reference_to_image":False,"text_to_image_set":True,"image_to_image_set":False,"multi_reference_to_image_set":False},"limits":{"min_reference_images":0,"max_reference_images":0,"max_output_images":6,"max_input_image_mb":0,"aspect_ratio_range":[0.33,3]},"provider_options_schema":{"size":{"type":"select","options":["1024*1024","1536*2688","2688*1536"]},"n":{"type":"number","min":1,"max":6},"prompt_extend":{"type":"boolean"},"watermark":{"type":"boolean"},"seed":{"type":"number","min":0,"max":2147483647},"negative_prompt":{"type":"string"}},"estimated_cost":0.1,"real_paid_allowed":True,"supports_external_task_id":True,"supports_task_query":True,"supports_cancel":False,"returns_asset_url":True,"returns_usage":True,"max_concurrent_tasks":1,"supports_text_to_image":True,"settle_missing_usage_with_estimated_cost":True}},
    {"name":"DALL-E 3","model_type":"image","provider":"openai","base_url":"https://api.openai.com/v1","model_name":"dall-e-3","config_json":{"default_size":"1024x1024","default_quality":"hd"}},
    {"name":"FLUX","model_type":"image","provider":"comfyui","base_url":"","model_name":"flux","config_json":{"default_size":"1024x1024","default_quality":"hd"}},
    {"name":"Seedance 2.0","model_type":"video","provider":"seedance","base_url":SEEDANCE_ARK_BASE_URL,"model_name":SEEDANCE_VIDEO_MODEL,"config_json":{"scene_key":"video_rendering","default_resolution":"720p","default_duration":5,"default_aspect_ratio":"9:16","max_duration_seconds":15}},
    {"name":"Kling 3.0","model_type":"video","provider":"kling","base_url":"","model_name":"kling-v1-6","config_json":{"default_resolution":"1080p","default_duration":5,"default_aspect_ratio":"9:16"}},
    {"name":"Wan 2.7","model_type":"video","provider":"wan","base_url":"https://dashscope.aliyuncs.com/api/v1","model_name":"wan2.7-i2v","config_json":{"scene_key":"video_rendering","default_resolution":"720P","default_duration":5,"default_aspect_ratio":"9:16","min_duration_seconds":2,"max_duration_seconds":15,"protocol":"dashscope_async","task_submit_path":"/services/aigc/video-generation/video-synthesis","task_query_path":"/tasks/{task_id}","capabilities":{"image_to_video":True,"text_to_video":False,"first_frame":True,"last_frame":True},"provider_options_schema":{"resolution":{"type":"select","options":["720P","1080P"]},"prompt_extend":{"type":"boolean"},"seed":{"type":"number","min":0,"max":2147483647},"duration":{"type":"number","min":2,"max":15},"negative_prompt":{"type":"string"}},"estimated_cost":0.35,"real_paid_allowed":True,"supports_external_task_id":True,"supports_task_query":True,"supports_cancel":False,"returns_asset_url":True,"returns_usage":True,"max_concurrent_tasks":1,"supports_image_to_video":True,"settle_missing_usage_with_estimated_cost":True}},
    {"name":"Pixelle Compose","model_type":"video","provider":"pixelle","base_url":"","model_name":PIXELLE_COMPOSE_MODEL,"config_json":{"scene_key":"video_composition","protocol":"pixelle_compose","default_resolution":"1080p","default_aspect_ratio":"9:16","supports_video_composition":True,"real_paid_allowed":True,"supports_external_task_id":True,"supports_task_query":True,"supports_cancel":False,"returns_asset_url":True,"returns_usage":True,"estimated_cost":0.01,"settle_missing_usage_with_estimated_cost":True,"max_concurrent_tasks":1}},
    {"name":"Edge-TTS","model_type":"tts","provider":"edge-tts","base_url":"","model_name":"edge-tts","config_json":{"default_voice":"zh-CN-XiaoxiaoNeural","default_language":"zh-CN","default_speed":1.0}},
    {"name":"Index-TTS","model_type":"tts","provider":"index-tts","base_url":"","model_name":"index-tts","config_json":{"default_voice":"","default_language":"zh-CN","default_speed":1.0}},
    {"name":"Spark-TTS","model_type":"tts","provider":"spark-tts","base_url":"","model_name":"spark-tts","config_json":{"default_voice":"","default_language":"zh-CN","default_speed":1.0}},
    {"name":"GPT-4o Audit","model_type":"audit","provider":"openai","base_url":"https://api.openai.com/v1","model_name":"gpt-4o","config_json":{"audit_mode":"single"}},
    {"name":"Gemini Audit","model_type":"audit","provider":"gemini","base_url":"","model_name":"gemini-2.5-pro","config_json":{"audit_mode":"single"}},
    {"name":"Bailian Qwen 3.7 Quality Audit","model_type":"audit","provider":"bailian","base_url":BAILIAN_COMPATIBLE_BASE_URL,"model_name":BAILIAN_QWEN_37_PLUS_MODEL,"sort_order":-100,"config_json":{"scene_key":"quality_audit","audit_mode":"single","protocol":"openai_chat_completions","supports_vision_audit":False,"thinking_enabled":False,"thinking_budget":8192,"max_tokens":8192,"temperature":0.1}},
    {"name":"Skip Audit","model_type":"audit","provider":"none","base_url":"","model_name":"","config_json":{"audit_mode":"skip"}},
]


def _merge_missing_config(existing: dict, defaults: dict, path: tuple[str, ...] = ()) -> dict:
    merged = dict(existing or {})
    for key, value in (defaults or {}).items():
        child_path = path + (key,)
        if key not in merged:
            merged[key] = value
        elif isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_missing_config(merged[key], value, child_path)
        elif child_path == ("scene_keys",) and isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = merged[key] + [item for item in value if item not in merged[key]]
    return merged


def _bailian_expert_review_entry() -> dict:
    return next(
        entry
        for entry in DEFAULT_MODELS
        if entry["provider"] == "bailian"
        and entry["model_type"] == "llm"
        and entry["model_name"] == BAILIAN_EXPERT_REVIEW_MODEL
    )


def _upgrade_legacy_expert_review_default(db: Session) -> None:
    entry = _bailian_expert_review_entry()
    legacy = db.query(AIModel).filter(
        AIModel.model_type == "llm",
        AIModel.provider == "openai-compatible",
        AIModel.model_name == "gpt-4o",
        AIModel.name == LEGACY_EXPERT_REVIEW_DEFAULT_NAME,
    ).first()
    if not legacy:
        return
    if legacy.api_key:
        return
    if (legacy.config_json or {}).get("scene_key") != "llm_agency_expert_review":
        return

    existing_bailian = db.query(AIModel).filter(
        AIModel.model_type == entry["model_type"],
        AIModel.provider == entry["provider"],
        AIModel.model_name == entry["model_name"],
    ).first()
    if existing_bailian and existing_bailian.id != legacy.id:
        legacy.enabled = False
        db.flush()
        return

    legacy.name = entry["name"]
    legacy.provider = entry["provider"]
    legacy.base_url = entry["base_url"]
    legacy.model_name = entry["model_name"]
    legacy.config_json = dict(entry["config_json"])
    db.flush()


def seed_ai_models(db: Session):
    """Seed default model configs. Idempotent."""
    _upgrade_legacy_expert_review_default(db)
    for entry in DEFAULT_MODELS:
        exists = db.query(AIModel).filter(
            AIModel.model_type == entry["model_type"],
            AIModel.provider == entry["provider"],
            AIModel.model_name == entry["model_name"],
        ).first()
        if not exists and entry["provider"] == "seedance":
            exists = db.query(AIModel).filter(
                AIModel.model_type == entry["model_type"],
                AIModel.provider == "seedance",
                AIModel.model_name.in_(LEGACY_SEEDANCE_MODEL_NAMES.get(entry["model_type"], ())),
            ).first()
            if exists:
                exists.name = entry["name"]
                exists.model_name = entry["model_name"]
                exists.base_url = entry["base_url"]
                exists.config_json = _merge_missing_config(exists.config_json or {}, entry["config_json"])
        if not exists:
            db.add(AIModel(**entry))
        elif entry["provider"] == "seedance":
            if exists.base_url == LEGACY_SEEDANCE_ARK_BASE_URL:
                exists.base_url = entry["base_url"]
            exists.config_json = _merge_missing_config(exists.config_json or {}, entry["config_json"])
        elif entry["provider"] in {"bailian", "pixelle"}:
            exists.config_json = _merge_missing_config(exists.config_json or {}, entry["config_json"])
    db.commit()
