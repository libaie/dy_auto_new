"""Model registry — resolves runtime model configuration by scene key."""
import logging
from sqlalchemy.orm import Session
from app.db_models import AIModel
from app.services.crypto import decrypt
from app.data.model_schema_data import scene_key_to_model_type, SCENES

logger = logging.getLogger(__name__)


class ModelResolutionError(Exception):
    """Raised when a model cannot be resolved for a scene."""
    def __init__(self, scene_key: str, repair_action: str, status_code: int = 400):
        self.scene_key = scene_key
        self.repair_action = repair_action
        self.status_code = status_code
        super().__init__(repair_action)


def _get_scene_label(scene_key: str) -> str:
    for scene in SCENES:
        if scene["key"] == scene_key:
            return scene["label"]
    return scene_key


def get_model_for_scene(
    db: Session,
    scene_key: str,
    explicit_model_id: str | None = None,
) -> dict:
    """
    Resolve a runtime model configuration for a scene.

    Resolution rules (in order):
    1. If explicit_model_id -> load and validate it supports the scene's model_type
    2. Otherwise -> first enabled model for the scene's model_type, by sort_order + created_at
    3. If nothing found -> raise ModelResolutionError with scene name and repair action

    Returns a dict with decrypted api_key + api_secret for runtime use.
    Never call this from list/schema/options endpoints — secrets are decrypted here.
    """
    model_type = scene_key_to_model_type(scene_key)
    scene_label = _get_scene_label(scene_key)

    if explicit_model_id:
        m = db.query(AIModel).filter(AIModel.id == explicit_model_id).first()
        if not m:
            raise ModelResolutionError(
                scene_key,
                f"选定的模型不存在或已被删除。请到 AI 模型配置中心为 {scene_label} 选择新模型。",
                status_code=400,
            )
        if not m.enabled:
            raise ModelResolutionError(
                scene_key,
                f"选定的模型 {m.name} 已被禁用。请到模型详情页启用该模型，或为 {scene_label} 选择其他模型。",
                status_code=400,
            )
        if m.model_type != model_type:
            raise ModelResolutionError(
                scene_key,
                f"模型 {m.name} 的类型为 {m.model_type}，不能用于 {scene_label}。请选择 {model_type} 类型的模型。",
                status_code=400,
            )
    else:
        m = (
            db.query(AIModel)
            .filter(AIModel.model_type == model_type, AIModel.enabled == True)
            .order_by(AIModel.sort_order, AIModel.created_at)
            .first()
        )
        if not m:
            raise ModelResolutionError(
                scene_key,
                f"未配置 {scene_label} 模型。请到 AI 模型配置中心新增或启用 {model_type} 类型的模型。",
                status_code=400,
            )

    ak = ""; asc = ""
    if m.api_key:
        try:
            ak = decrypt(m.api_key)
        except Exception:
            logger.warning("decrypt api_key failed for model %s", m.id)
    if m.api_secret:
        try:
            asc = decrypt(m.api_secret)
        except Exception:
            logger.warning("decrypt api_secret failed for model %s", m.id)

    return {
        "id": m.id,
        "name": m.name,
        "scene_key": scene_key,
        "model_type": m.model_type,
        "provider": m.provider,
        "base_url": m.base_url or "",
        "model_name": m.model_name or "",
        "api_key": ak,
        "api_secret": asc,
        "config_json": m.config_json or {},
        "resolution_source": "explicit" if explicit_model_id else "default",
    }
