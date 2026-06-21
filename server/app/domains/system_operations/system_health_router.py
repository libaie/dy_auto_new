"""系统运营业务域模块。

系统运营业务域，负责健康检查、对象存储和运维状态接口。本文件负责 system_health_router 相关业务规则、状态转换和外部系统边界。
"""

import os

from fastapi import APIRouter, Depends
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.db.models import (
    AIModel,
    ProductionAuditEvent,
    ProviderCostReservation,
    ProviderStageTask,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)
from app.deps import verify_admin_token
from app.domains.video_production.provider_capability_service import capability_from_model_config
from app.domains.video_production.provider_stage_executor import PROVIDER_SUBMIT_WORKER_COUNT_ENV


router = APIRouter(prefix="/api/system", tags=["system"])


_REQUIRED_SCHEMA_MODELS = (
    ProviderStageTask,
    ProviderCostReservation,
    VideoProductionRun,
    VideoProductionAsset,
    VideoReviewRecord,
    ProductionAuditEvent,
)

_PROVIDER_CAPABILITY_REQUIRED = (
    "real_paid_allowed",
    "supports_external_task_id",
    "supports_task_query",
    "returns_asset_url",
    "returns_usage",
)
_SCENE_CAPABILITY_REQUIRED = {
    "image_generation": ("supports_text_to_image",),
    "video_rendering": ("supports_image_to_video",),
    "video_composition": ("supports_video_composition",),
}
_REAL_PROVIDER_SCENE_KEYS = (
    "image_generation",
    "video_rendering",
    "video_composition",
)


def _required_schema() -> dict[str, list[str]]:
    return {
        model.__tablename__: [column.name for column in model.__table__.columns]
        for model in _REQUIRED_SCHEMA_MODELS
    }


def _migration_health(db: Session) -> dict:
    try:
        required_schema = _required_schema()
        inspector = inspect(db.get_bind())
        existing_tables = set(inspector.get_table_names())
        missing_tables = sorted(set(required_schema) - existing_tables)
        missing_columns = []

        for table_name, required_columns in required_schema.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            missing_columns.extend(
                f"{table_name}.{column_name}"
                for column_name in required_columns
                if column_name not in existing_columns
            )
    except SQLAlchemyError as exc:
        return {
            "status": "blocked",
            "missing_tables": [],
            "missing_columns": [],
            "repair_actions": ["Check database connectivity and migration state."],
            "error": str(exc),
        }

    repair_actions = []
    if missing_tables or missing_columns:
        repair_actions.append("Run alembic upgrade head before enabling real paid execution.")

    return {
        "status": "blocked" if repair_actions else "ok",
        "missing_tables": missing_tables,
        "missing_columns": sorted(missing_columns),
        "repair_actions": repair_actions,
    }


def _capability_for_model(model: AIModel) -> dict:
    config_json = model.config_json if isinstance(model.config_json, dict) else {}
    return capability_from_model_config(
        {
            "config_json": config_json,
            "provider_options": config_json.get("provider_options"),
            "capability": config_json.get("capability") or config_json.get("capabilities"),
        }
    )


def _model_config(model: AIModel) -> dict:
    return model.config_json if isinstance(model.config_json, dict) else {}


def _model_summary(model: AIModel, capability: dict | None = None) -> dict:
    payload = {
        "model_id": getattr(model, "id", None),
        "provider": getattr(model, "provider", None),
        "model_name": getattr(model, "model_name", None),
    }
    if capability is not None:
        payload["max_concurrent_tasks"] = capability.get("max_concurrent_tasks")
    return payload


def _positive_estimated_cost(model: AIModel) -> bool:
    config = _model_config(model)
    candidates = [
        config.get("estimated_cost"),
        config.get("cost"),
    ]
    for key in ("provider_options", "capability", "capabilities"):
        value = config.get(key)
        if isinstance(value, dict):
            candidates.extend([value.get("estimated_cost"), value.get("cost")])
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            if float(candidate) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _worker_runtime_health() -> dict:
    raw_count = os.getenv(PROVIDER_SUBMIT_WORKER_COUNT_ENV)
    status = "ok" if raw_count == "1" else "blocked"
    repair_actions = []
    if status != "ok":
        repair_actions.append(
            f"Set {PROVIDER_SUBMIT_WORKER_COUNT_ENV}=1 before enabling real paid provider execution."
        )
    return {
        "status": status,
        "env": PROVIDER_SUBMIT_WORKER_COUNT_ENV,
        "value": raw_count,
        "repair_actions": repair_actions,
    }


def _missing_real_provider_requirements(model: AIModel, capability: dict, scene_key: str | None = None) -> list[str]:
    missing = [
        key for key in _PROVIDER_CAPABILITY_REQUIRED
        if capability.get(key) is not True
    ]
    if scene_key:
        missing.extend(
            key for key in _SCENE_CAPABILITY_REQUIRED.get(scene_key, ())
            if capability.get(key) is not True
        )
    if not getattr(model, "api_key", None):
        missing.append("api_key")
    if not getattr(model, "base_url", None):
        missing.append("base_url")
    if not getattr(model, "model_name", None):
        missing.append("model_name")
    if not _positive_estimated_cost(model):
        missing.append("estimated_cost")
    return missing


def _scene_readiness(models: list[AIModel]) -> dict[str, dict]:
    readiness = {}
    for scene_key in _REAL_PROVIDER_SCENE_KEYS:
        scene_models = [
            model for model in models
            if _model_config(model).get("scene_key") == scene_key
        ]
        ready = []
        blocked = []
        for model in scene_models:
            capability = _capability_for_model(model)
            missing = _missing_real_provider_requirements(model, capability, scene_key)
            if missing:
                blocked.append({**_model_summary(model), "missing": missing})
            else:
                ready.append(_model_summary(model, capability))
        repair_actions = []
        if not ready:
            repair_actions.append(
                f"Configure one enabled paid-ready model for scene_key '{scene_key}'."
            )
        readiness[scene_key] = {
            "status": "ok" if ready else "blocked",
            "ready": ready,
            "blocked": blocked,
            "repair_actions": repair_actions,
        }
    return readiness


def _provider_capability_error(status: str, error: Exception, repair_action: str) -> dict:
    return {
        "status": status,
        "checked_model_count": 0,
        "paid_ready_count": 0,
        "paid_ready": [],
        "blocked_for_real_provider": [],
        "worker_runtime": _worker_runtime_health(),
        "scene_readiness": {
            scene_key: {
                "status": "blocked",
                "ready": [],
                "blocked": [],
                "repair_actions": [repair_action],
            }
            for scene_key in _REAL_PROVIDER_SCENE_KEYS
        },
        "repair_actions": [repair_action],
        "error": str(error),
    }


def _provider_capability_health(db: Session) -> dict:
    try:
        models = db.query(AIModel).filter(AIModel.enabled == True).all()
        paid_ready = []
        blocked = []

        for model in models:
            capability = _capability_for_model(model)
            missing = _missing_real_provider_requirements(model, capability)
            summary = _model_summary(model)
            if missing:
                blocked.append({**summary, "missing": missing})
            else:
                paid_ready.append(_model_summary(model, capability))
    except SQLAlchemyError as exc:
        return _provider_capability_error(
            "blocked",
            exc,
            "Check ai_models table availability and migration state.",
        )
    except (AttributeError, TypeError, ValueError) as exc:
        return _provider_capability_error(
            "warning",
            exc,
            "Fix malformed provider model capability configuration.",
        )

    worker_runtime = _worker_runtime_health()
    scene_readiness = _scene_readiness(models)
    repair_actions = []
    if worker_runtime["status"] != "ok":
        repair_actions.extend(worker_runtime["repair_actions"])
    for scene_key, scene in scene_readiness.items():
        if scene["status"] != "ok":
            repair_actions.extend(scene["repair_actions"])
    if not paid_ready:
        repair_actions.append(
            "Configure at least one enabled real provider model with paid execution, external task IDs, task query, asset URLs, usage reporting, and positive estimated cost."
        )
    status = "ok"
    if repair_actions:
        status = "blocked"

    return {
        "status": status,
        "checked_model_count": len(models),
        "paid_ready_count": len(paid_ready),
        "paid_ready": paid_ready,
        "blocked_for_real_provider": blocked,
        "worker_runtime": worker_runtime,
        "scene_readiness": scene_readiness,
        "repair_actions": repair_actions,
    }


@router.get("/health")
def system_health(db: Session = Depends(get_db), _user=Depends(verify_admin_token)):
    migration = _migration_health(db)
    provider_capability = _provider_capability_health(db)
    status = "ok"
    if migration["status"] == "blocked" or provider_capability["status"] == "blocked":
        status = "blocked"
    elif provider_capability["status"] != "ok":
        status = "warning"

    return {
        "ok": True,
        "status": status,
        "migration": migration,
        "provider_capability": provider_capability,
        "latest_paid_smoke": None,
    }
