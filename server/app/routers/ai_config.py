"""AI 模型配置中心 — CRUD 管理所有 AI 模型配置."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import SystemSetting
from app.services.crypto import encrypt, decrypt, is_sensitive_key

router = APIRouter(prefix="/api/ai-config", tags=["ai-config"])

AI_CONFIG_KEYS = [
    "seedance_api_key", "kling_access_key", "kling_secret_key",
    "runninghub_api_key", "comfyui_url", "comfyui_api_key",
    "llm_provider", "llm_api_key", "llm_base_url", "llm_model",
    "oss_provider", "oss_endpoint", "oss_bucket", "oss_access_key", "oss_secret_key",
    "audit_model_multi", "audit_model_single", "audit_model_batch",
]


@router.get("/models")
def list_models(db: Session = Depends(get_db)):
    """读取所有 AI 配置. 敏感字段只返回占位符，不暴露任何真实值."""
    rows = db.query(SystemSetting).filter(SystemSetting.key.in_(AI_CONFIG_KEYS)).all()
    result = {}
    for r in rows:
        if is_sensitive_key(r.key):
            result[r.key] = "****" if r.value else ""
        else:
            result[r.key] = r.value or ""
    return {"ok": True, "models": result}


@router.put("/models")
def update_models(body: dict, db: Session = Depends(get_db),
                  _: str = Depends(verify_admin_token)):
    """批量更新 AI 配置. 敏感字段自动加密存储."""
    for key, value in body.items():
        if key not in AI_CONFIG_KEYS:
            continue
        store_value = encrypt(str(value)) if is_sensitive_key(key) else str(value)
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if row:
            row.value = store_value
        else:
            db.add(SystemSetting(key=key, value=store_value))
    db.commit()
    return {"ok": True}
