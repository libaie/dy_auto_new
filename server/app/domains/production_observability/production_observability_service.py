"""生产观测业务域模块。

生产观测业务域，负责生产事件、指标和运行证据聚合。本文件负责 production_observability_service 相关业务规则、状态转换和外部系统边界。
"""

import re
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.production_observability import ProductionAuditEvent


SECRET_KEYS = {
    "accesstoken",
    "apikey",
    "apisecret",
    "authorization",
    "bearertoken",
    "clientsecret",
    "password",
    "privatekey",
    "refreshtoken",
    "secret",
    "secretkey",
    "token",
    "xapikey",
}


def _normalize_key(key: str) -> str:
    """业务函数：处理 _normalize_key 对应的业务流程、校验或数据转换。"""
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _redact(value: Any) -> Any:
    """业务函数：处理 _redact 对应的业务流程、校验或数据转换。"""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if isinstance(key, str) and _normalize_key(key) in SECRET_KEYS
            else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def record_production_event(
    db: Session,
    *,
    event_type: str,
    run_id: str | None = None,
    production_plan_id: str | None = None,
    production_episode_id: str | None = None,
    production_segment_id: str | None = None,
    provider_task_id: str | None = None,
    payload: dict | None = None,
) -> ProductionAuditEvent:
    """业务函数：处理 record_production_event 对应的业务流程、校验或数据转换。"""
    event = ProductionAuditEvent(
        event_type=event_type,
        run_id=run_id,
        production_plan_id=production_plan_id,
        production_episode_id=production_episode_id,
        production_segment_id=production_segment_id,
        provider_task_id=provider_task_id,
        payload_json=_redact(payload or {}),
    )
    db.add(event)
    db.flush()
    return event
