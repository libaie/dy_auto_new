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
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _redact(value: Any) -> Any:
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
