"""模型配置业务域模块。

模型配置业务域，负责 AI 模型注册、运行时配置解析和连接检测。本文件负责 migration 相关业务规则、状态转换和外部系统边界。
"""

import logging
import os
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.models.model_configuration import AIModel
from app.domains.system_configuration.crypto import encrypt

logger = logging.getLogger(__name__)

SEEDANCE_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3"
SEEDANCE_VIDEO_MODEL = "doubao-seedance-2.0"
LEGACY_SEEDANCE_VIDEO_MODELS = (
    "doubao-seedance-2.0-260128",
    "doubao-seedance-2-0-260128",
)


def _normalize_model_name(name: str | None) -> str:
    """业务函数：处理 _normalize_model_name 对应的业务流程、校验或数据转换。

    入参：name 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Normalize NULL/empty model_name to empty string for dedup matching."""
    if name is None:
        return ""
    return str(name).strip()


def _find_existing(db: Session, model_type: str, provider: str, model_name: str | None) -> AIModel | None:
    """业务函数：处理 _find_existing 对应的业务流程、校验或数据转换。

    入参：db、model_type、provider、model_name 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Find an existing AIModel with matching type+provider+name, handling NULL/empty."""
    normalized = _normalize_model_name(model_name)
    q = db.query(AIModel).filter(
        AIModel.model_type == model_type,
        AIModel.provider == provider,
    )
    q = q.filter(or_(
        AIModel.model_name == normalized,
        AIModel.model_name.is_(None),
    ))
    return q.first()


def migrate_legacy_settings(db: Session) -> dict:
    """业务函数：处理 migrate_legacy_settings 对应的业务流程、校验或数据转换。

    入参：db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """
    Migrate legacy Settings/Pixelle/Seedance config into AIModel.

    Returns: {created: int, skipped: int, conflicts: list[dict]}
    Rules:
    - Only INSERT — never UPDATE existing rows
    - If a duplicate exists -> skip, add to conflicts list
    - Secrets are encrypted using the existing crypto service
    - Idempotent: safe to re-run
    """
    result = {"created": 0, "skipped": 0, "conflicts": []}

    # 1. Settings LLM keys -> script_generation
    try:
        from app.config import _resolve_ai_config
        cfg = _resolve_ai_config(db)
    except Exception:
        cfg = {}

    if cfg:
        llm_provider = cfg.get("llm_provider") or cfg.get("provider", "openai")
        llm_key = cfg.get("llm_api_key") or cfg.get("api_key", "")
        llm_model = cfg.get("llm_model") or cfg.get("model_name", "")
        llm_base = cfg.get("llm_base_url") or cfg.get("base_url", "")
        if llm_key:
            existing = _find_existing(db, "llm", llm_provider, llm_model)
            if existing:
                result["conflicts"].append({
                    "source": "Settings LLM",
                    "provider": llm_provider,
                    "reason": "duplicate — model already exists",
                    "existing_id": existing.id,
                })
                result["skipped"] += 1
            else:
                db.add(AIModel(
                    name=f"{llm_provider.title()} (Legacy)",
                    model_type="llm",
                    provider=llm_provider,
                    base_url=llm_base or None,
                    api_key=encrypt(llm_key),
                    model_name=_normalize_model_name(llm_model),
                    config_json={"scene_key": "script_generation", "migrated_from": "settings"},
                ))
                result["created"] += 1

    # 2. Seedance API key -> video_rendering
    seedance_key = os.getenv("SEEDANCE_API_KEY", "")
    if seedance_key:
        existing = _find_existing(db, "video", "seedance", SEEDANCE_VIDEO_MODEL)
        for legacy_model in LEGACY_SEEDANCE_VIDEO_MODELS:
            existing = existing or _find_existing(db, "video", "seedance", legacy_model)
        if existing:
            result["conflicts"].append({
                "source": "Seedance env",
                "provider": "seedance",
                "reason": "duplicate — model already exists",
                "existing_id": existing.id,
            })
            result["skipped"] += 1
        else:
            db.add(AIModel(
                name="Seedance 2.0 (Legacy)",
                model_type="video",
                provider="seedance",
                base_url=SEEDANCE_ARK_BASE_URL,
                api_key=encrypt(seedance_key),
                model_name=SEEDANCE_VIDEO_MODEL,
                config_json={"scene_key": "video_rendering", "migrated_from": "env"},
            ))
            result["created"] += 1

    # 3. Pixelle — migrate model credentials, NOT service config
    from app.config import PIXELLE_VIDEO_URL
    pixelle_url = PIXELLE_VIDEO_URL
    if pixelle_url and pixelle_url != "http://localhost:8500":
        existing = _find_existing(db, "image", "pixelle", "")
        if existing:
            result["conflicts"].append({
                "source": "Pixelle config",
                "provider": "pixelle",
                "reason": "duplicate — model already exists",
                "existing_id": existing.id,
            })
            result["skipped"] += 1
        else:
            db.add(AIModel(
                name="Pixelle (Legacy)",
                model_type="image",
                provider="pixelle",
                base_url=pixelle_url,
                model_name="",
                config_json={
                    "scene_key": "image_generation",
                    "migrated_from": "config.py",
                    "pixelle_timeout": 600,
                },
            ))
            result["created"] += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Migration commit failed: %s", e)
        result["error"] = str(e)

    logger.info("Migration complete: created=%d skipped=%d conflicts=%d",
                result["created"], result["skipped"], len(result["conflicts"]))
    return result
