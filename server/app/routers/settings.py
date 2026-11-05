"""System settings API — key-value config store for admin UI."""
import logging
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.db_models import SystemSetting
from app.deps import verify_admin_token, require_role
from app.models import SettingUpdate
from app.config import _resolve_ai_config, _resolve_pixelle_config
from app.services.crypto import encrypt
from app.services.decision_config import (
    DECISION_API_URL,
    DECISION_MODEL,
    get_decision_settings,
    get_public_decision_config,
    validate_decision_settings,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Keys whose values are masked in GET responses (never sent to client)
_SENSITIVE_KEYS = {"ai_api_key", "llm_api_key", "pixelle_api_key", "decision_api_key"}
_MASKED_VALUE = "****"
_GENERATION_ALIASES = {
    "ai_api_key": "llm_api_key",
    "ai_base_url": "llm_base_url",
    "ai_model": "llm_model",
    "ai_thinking": "llm_thinking",
}


@router.get("")
def get_settings(
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        rows = db.query(SystemSetting).all()
        result = {}
        for s in rows:
            if s.key in _SENSITIVE_KEYS:
                result[s.key] = _MASKED_VALUE
            else:
                result[s.key] = s.value
    except OperationalError:
        logger.warning("System settings unavailable; refusing to return editable defaults")
        raise HTTPException(status_code=503, detail="Settings unavailable; retry later") from None
    stored_values = {row.key: row.value for row in rows}
    # The form must display the same effective values used by model callers.
    # Otherwise saving an unrelated decision setting persists UI defaults over
    # environment-backed generation/video configuration.
    generation = _resolve_ai_config(db, settings_snapshot=stored_values)
    result.update({
        "ai_base_url": generation["base_url"],
        "ai_model": generation["model"],
        "ai_thinking": generation["thinking_level"],
    })
    if generation["api_key"]:
        result["ai_api_key"] = _MASKED_VALUE
    else:
        result.pop("ai_api_key", None)
    video = _resolve_pixelle_config(db, settings_snapshot=stored_values)
    result.update({"pixelle_video_url": video["url"], "pixelle_video_timeout": str(video["timeout"])})
    try:
        # Include effective environment-backed values so saving the form does not
        # accidentally disable a provider that was configured on the server.
        result.update(get_decision_settings(db, settings_snapshot=stored_values))
    except ValueError:
        # A bad threshold must not hide enabled state or other valid overrides.
        public = get_public_decision_config(db, settings_snapshot=stored_values)
        result["decision_enabled"] = "true" if public["enabled"] else "false"
        for key, default in {
            "decision_api_url": DECISION_API_URL,
            "decision_model": DECISION_MODEL,
            "decision_min_confidence": "0.5",
            "decision_min_probability": "0.75",
        }.items():
            result.setdefault(key, os.getenv(key.upper(), default))
        result.setdefault("decision_api_key", _MASKED_VALUE if os.getenv("DECISION_API_KEY", "") else "")
        result["decision_config_error"] = "Jev 配置无效，请检查服务端环境变量或重新保存决策配置"
    return result


@router.put("")
def update_settings(
    request: SettingUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    pending = dict(request.settings)
    try:
        validate_decision_settings(pending)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    decision_key = pending.get("decision_api_key")
    if decision_key is not None:
        decision_key = decision_key.strip()
        if not decision_key or decision_key == _MASKED_VALUE:
            pending.pop("decision_api_key")
        else:
            encryption_key = os.getenv("ENCRYPTION_KEY", "").strip()
            if not encryption_key or encryption_key == "dy-auto-default-key-change-me":
                raise HTTPException(status_code=503, detail="请先在服务端配置 ENCRYPTION_KEY，再保存决策 API Key")
            try:
                pending["decision_api_key"] = encrypt(decision_key)
            except Exception:
                raise HTTPException(status_code=503, detail="决策 API Key 加密失败，请检查服务端加密配置") from None

    # Existing llm_* settings take precedence at runtime. Keep a form edit of
    # its ai_* alias effective without changing explicitly supplied llm_* values.
    try:
        current_keys = {row.key for row in db.query(SystemSetting).filter(
            SystemSetting.key.in_(_GENERATION_ALIASES.values())
        ).all()}
    except OperationalError:
        # Without this snapshot an ai_* edit may report success while an
        # existing llm_* value keeps taking precedence. Apply nothing on failure.
        raise HTTPException(status_code=503, detail="Settings unavailable; retry later") from None
    for legacy, current in _GENERATION_ALIASES.items():
        if legacy in pending and current in current_keys and current not in pending:
            if not (legacy in _SENSITIVE_KEYS and pending[legacy] == _MASKED_VALUE):
                pending[current] = pending[legacy]

    for key, value in pending.items():
        # Skip masked values — client sent placeholder, don't overwrite real secret
        if value == _MASKED_VALUE and key in _SENSITIVE_KEYS:
            continue
        try:
            existing = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        except OperationalError:
            logger.warning("system_settings table missing, attempting create")
            from app.database import init_db
            init_db()
            existing = None
        if existing:
            existing.value = value
        else:
            db.add(SystemSetting(key=key, value=value))
    db.commit()
    return {"updated": len(request.settings)}
