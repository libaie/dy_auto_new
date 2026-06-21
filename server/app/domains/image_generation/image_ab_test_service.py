"""图片生成业务域模块。

图片生成业务域，负责图片任务创建、策略选择、审核门禁和生成资产入库。本文件负责 image_ab_test_service 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db.models.image_production import (
    ImageCreationAsset,
    ImageCreationTask,
    ImageProductionAbAttempt,
    ImageProductionAbGroup,
    ImageProductionStrategy,
)
from app.db.models import (
    ProductionAuditEvent,
)
from app.domains.image_generation.image_creation_errors import image_error
from app.domains.image_generation.image_creation_service import (
    _apply_strategy_defaults,
    _resolve_reference_images,
    _resolve_source_asset,
    create_image_task,
    normalized_request_hash,
    task_payload,
)
from app.domains.image_generation.image_production_metrics_service import refresh_image_strategy_metrics, strategy_metrics_payload
from app.domains.image_generation.image_production_recommendation_service import ab_winner_recommendation_payload
from app.domains.image_generation.image_selection_preview_service import create_selection_preview
from app.domains.production_observability.production_observability_service import record_production_event


TERMINAL_TASK_STATUSES = {"completed", "failed", "cancelled", "completed_with_warnings"}
DECISION_STATUSES = {"winner_selected", "no_winner"}
INCOMPLETE_ATTEMPT_STATUSES = {"creating", "running"}
INCOMPLETE_ATTEMPT_STALE_AFTER = timedelta(minutes=10)
AB_ERROR_MAX_LENGTH = 500
LOGICAL_HASH_EXCLUDED_FIELDS = {
    "ab_test_group_id",
    "cost_confirmation",
    "idempotency_key",
    "preview_request_hash",
    "selection_preview_id",
    "selection_preview_request_hash",
    "strategy_id",
    "strategy_ids",
    "strategy_version",
    "user_id",
}


def _stable_json(value: Any) -> str:
    """业务函数：处理 _stable_json 对应的业务流程、校验或数据转换。"""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))


def _hash(value: Any) -> str:
    """业务函数：处理 _hash 对应的业务流程、校验或数据转换。"""
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _unique_strategy_ids(strategy_ids: list[str]) -> list[str]:
    """业务函数：处理 _unique_strategy_ids 对应的业务流程、校验或数据转换。"""
    return [strategy_id for index, strategy_id in enumerate(strategy_ids) if strategy_id not in strategy_ids[:index]]


def _normalized_group_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """业务函数：处理 _normalized_group_payload 对应的业务流程、校验或数据转换。"""
    normalized = dict(payload)
    if "strategy_ids" in normalized:
        normalized["strategy_ids"] = _unique_strategy_ids(list(normalized.get("strategy_ids") or []))
    return normalized


def _canonical_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """业务函数：处理 _canonical_request_payload 对应的业务流程、校验或数据转换。"""
    return {
        key: value
        for key, value in payload.items()
        if key not in LOGICAL_HASH_EXCLUDED_FIELDS
    }


def _record(db: Session, event_type: str, payload: dict[str, Any]) -> None:
    """业务函数：处理 _record 对应的业务流程、校验或数据转换。"""
    record_production_event(db, event_type=event_type, payload={"scope": "image_ab", **payload})


def _safe_ab_error_message(value: Any) -> str:
    """业务函数：处理 _safe_ab_error_message 对应的业务流程、校验或数据转换。"""
    message = str(value or "")
    message = re.sub(r"(?i)\bauthorization\s*[:=]\s*bearer\s+[^\s,;]+", "authorization=[REDACTED]", message)
    message = re.sub(r"(?i)\bbearer\s+[^\s,;]+", "Bearer [REDACTED]", message)
    message = re.sub(
        r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|bearer[_-]?token|token|secret|password|authorization)\b\s*[:=]\s*[^\s,;]+",
        lambda match: f"{match.group(1)}=[REDACTED]",
        message,
    )
    if len(message) > AB_ERROR_MAX_LENGTH:
        message = f"{message[:AB_ERROR_MAX_LENGTH]}..."
    return message


def _strategy_rows(db: Session, strategy_ids: list[str]) -> list[ImageProductionStrategy]:
    """业务函数：处理 _strategy_rows 对应的业务流程、校验或数据转换。"""
    unique_ids = _unique_strategy_ids(strategy_ids)
    if len(unique_ids) < 2 or len(unique_ids) > 4:
        raise image_error(
            422,
            "IMAGE_AB_TEST_STRATEGY_COUNT_INVALID",
            "A/B comparison requires two to four unique strategies.",
            "Select two to four image production strategies.",
            retryable=False,
        )

    rows = db.query(ImageProductionStrategy).filter(ImageProductionStrategy.id.in_(unique_ids)).all()
    by_id = {row.id: row for row in rows}
    missing = [strategy_id for strategy_id in unique_ids if strategy_id not in by_id]
    if missing:
        raise image_error(
            404,
            "IMAGE_STRATEGY_NOT_FOUND",
            "One or more A/B strategies were not found.",
            "Reload strategies and retry.",
            retryable=False,
            affected_ids=missing,
        )

    inactive = [row.id for row in rows if row.status != "active"]
    if inactive:
        raise image_error(
            422,
            "IMAGE_AB_TEST_STRATEGY_INACTIVE",
            "One or more A/B strategies are not active.",
            "Choose active strategies.",
            retryable=False,
            affected_ids=inactive,
        )
    return [by_id[strategy_id] for strategy_id in unique_ids]


def _payload_for_strategy(
    payload: dict[str, Any],
    strategy: ImageProductionStrategy,
    *,
    for_preview: bool = False,
) -> dict[str, Any]:
    """业务函数：处理 _payload_for_strategy 对应的业务流程、校验或数据转换。"""
    task_payload = dict(payload)
    task_payload.pop("strategy_ids", None)
    task_payload.pop("preview_request_hash", None)
    task_payload.pop("selection_preview_id", None)
    task_payload.pop("selection_preview_request_hash", None)
    task_payload["strategy_id"] = strategy.id
    task_payload["strategy_version"] = strategy.version
    if for_preview:
        task_payload.pop("idempotency_key", None)
        task_payload.pop("cost_confirmation", None)
    return task_payload


def _amount(preview: dict[str, Any]) -> float:
    """业务函数：处理 _amount 对应的业务流程、校验或数据转换。"""
    return float((preview.get("cost_estimate") or {}).get("amount") or 0)


def _currency(previews: list[dict[str, Any]]) -> str:
    """业务函数：处理 _currency 对应的业务流程、校验或数据转换。"""
    for preview in previews:
        currency = (preview.get("cost_estimate") or {}).get("currency")
        if currency:
            return currency
    return "CNY"


def _group_cap(previews: list[dict[str, Any]]) -> float | None:
    """业务函数：处理 _group_cap 对应的业务流程、校验或数据转换。"""
    values = [
        float(preview["cost_estimate"]["ab_max_group_cost"])
        for preview in previews
        if (preview.get("cost_estimate") or {}).get("ab_max_group_cost") is not None
    ]
    return min(values) if values else None


def _total_cost(previews: list[dict[str, Any]]) -> dict[str, Any]:
    """业务函数：处理 _total_cost 对应的业务流程、校验或数据转换。"""
    amount = sum(_amount(preview) for preview in previews)
    cap = _group_cap(previews)
    return {
        "amount": amount,
        "currency": _currency(previews),
        "requires_confirmation": any((preview.get("cost_estimate") or {}).get("requires_confirmation") for preview in previews),
        "ab_max_group_cost": cap,
        "cost_limit_exceeded": cap is not None and amount > cap,
    }


def _logical_request_hash(payload: dict[str, Any], strategies: list[ImageProductionStrategy]) -> str:
    """业务函数：处理 _logical_request_hash 对应的业务流程、校验或数据转换。"""
    return _hash({
        "payload": _canonical_request_payload(payload),
        "strategy_ids": [strategy.id for strategy in strategies],
        "strategy_versions": [strategy.version for strategy in strategies],
    })


def _ab_request_hash(payload: dict[str, Any], strategies: list[ImageProductionStrategy], preview_hashes: list[str | None]) -> str:
    """业务函数：处理 _ab_request_hash 对应的业务流程、校验或数据转换。"""
    return _hash({
        "logical_request_hash": _logical_request_hash(payload, strategies),
        "preview_hashes": preview_hashes,
    })


def _preview_drift() -> HTTPException:
    """业务函数：处理 _preview_drift 对应的业务流程、校验或数据转换。"""
    return image_error(
        409,
        "IMAGE_AB_TEST_PREVIEW_DRIFT",
        "A/B preview no longer matches this request.",
        "Run A/B preview again before creating tasks.",
        retryable=False,
    )


def _valid_preview_hash(value: Any) -> bool:
    """业务函数：处理 _valid_preview_hash 对应的业务流程、校验或数据转换。"""
    return isinstance(value, str) and bool(value.strip())


def _build_ab_preview(
    db: Session,
    payload: dict[str, Any],
    user_id: str | None = None,
    strategies: list[ImageProductionStrategy] | None = None,
) -> dict[str, Any]:
    """业务函数：处理 _build_ab_preview 对应的业务流程、校验或数据转换。"""
    strategies = strategies or _strategy_rows(db, list(payload.get("strategy_ids") or []))
    previews = []
    for strategy in strategies:
        preview = create_selection_preview(db, _payload_for_strategy(payload, strategy, for_preview=True), user_id=user_id)
        if ("ok" in preview and preview.get("ok") is not True) or not _valid_preview_hash(preview.get("request_hash")):
            raise _preview_drift()
        preview["strategy_id"] = strategy.id
        preview["strategy_version"] = strategy.version
        previews.append(preview)

    total_cost = _total_cost(previews)
    preview_hashes = [preview.get("request_hash") for preview in previews]
    logical_request_hash = _logical_request_hash(payload, strategies)
    request_hash = _ab_request_hash(payload, strategies, preview_hashes)
    result = {
        "ok": True,
        "request_hash": request_hash,
        "logical_request_hash": logical_request_hash,
        "strategy_count": len(strategies),
        "total_cost_estimate": total_cost,
        "previews": previews,
    }
    return result


def preview_ab_group(db: Session, payload: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    """业务函数：处理 preview_ab_group 对应的业务流程、校验或数据转换。"""
    result = _build_ab_preview(db, payload, user_id=user_id)
    _record(db, "image_ab.preview", {
        "request_hash": result["request_hash"],
        "logical_request_hash": result["logical_request_hash"],
        "canonical_payload": _canonical_request_payload(payload),
        "user_id": user_id,
        "strategy_count": result["strategy_count"],
        "strategy_ids": [preview["strategy_id"] for preview in result["previews"]],
        "strategy_versions": [preview["strategy_version"] for preview in result["previews"]],
        "preview_hashes": [preview.get("request_hash") for preview in result["previews"]],
        "total_cost_estimate": result["total_cost_estimate"],
        "previews": result["previews"],
    })
    db.commit()
    return result


def _ensure_preview_matches(
    db: Session,
    payload: dict[str, Any],
    user_id: str | None,
    strategies: list[ImageProductionStrategy] | None = None,
) -> dict[str, Any]:
    """业务函数：处理 _ensure_preview_matches 对应的业务流程、校验或数据转换。"""
    preview = _build_ab_preview(db, payload, user_id=user_id, strategies=strategies)
    expected_hash = payload.get("preview_request_hash")
    if not expected_hash or expected_hash != preview["request_hash"]:
        raise image_error(
            409,
            "IMAGE_AB_TEST_PREVIEW_DRIFT",
            "A/B preview no longer matches this request.",
            "Run A/B preview again before creating tasks.",
            retryable=False,
        )
    if preview["total_cost_estimate"]["cost_limit_exceeded"]:
        raise image_error(
            409,
            "IMAGE_AB_TEST_COST_LIMIT_EXCEEDED",
            "A/B comparison exceeds the configured group cost limit.",
            "Reduce count, choose cheaper strategies, or adjust policy.",
            retryable=False,
            details={"total_cost_estimate": preview["total_cost_estimate"]},
        )
    return preview


def _attempt_key(payload: dict[str, Any], group: ImageProductionAbGroup, index: int, strategy: ImageProductionStrategy) -> str:
    """业务函数：处理 _attempt_key 对应的业务流程、校验或数据转换。"""
    base_key = payload.get("idempotency_key") or group.id
    return f"{base_key}:attempt:{index}:{strategy.id}:{strategy.version}"


def _attempt_key_for_existing_attempt(group: ImageProductionAbGroup, index: int, attempt: ImageProductionAbAttempt) -> str:
    """业务函数：处理 _attempt_key_for_existing_attempt 对应的业务流程、校验或数据转换。"""
    base_key = group.idempotency_key or group.id
    return f"{base_key}:attempt:{index}:{attempt.strategy_id}:{attempt.strategy_version}"


def _idempotency_conflict(existing: ImageProductionAbGroup | None = None, *, expose_existing_id: bool = True) -> HTTPException:
    """业务函数：处理 _idempotency_conflict 对应的业务流程、校验或数据转换。"""
    return image_error(
        409,
        "IMAGE_AB_TEST_IDEMPOTENCY_CONFLICT",
        "A/B idempotency key was reused for a different request.",
        "Use a new idempotency key or restore the original request.",
        retryable=False,
        affected_ids=[existing.id] if existing is not None and expose_existing_id else None,
    )


def _group_has_decision(group: ImageProductionAbGroup) -> bool:
    """业务函数：处理 _group_has_decision 对应的业务流程、校验或数据转换。"""
    return bool(group.winner_attempt_id or group.status in DECISION_STATUSES or group.decision_json)


def _normalize_datetime_for_compare(value: datetime | None, now: datetime) -> datetime | None:
    """业务函数：处理 _normalize_datetime_for_compare 对应的业务流程、校验或数据转换。"""
    if value is None:
        return None
    if value.tzinfo is not None and now.tzinfo is None:
        return value.replace(tzinfo=None)
    if value.tzinfo is None and now.tzinfo is not None:
        return value.replace(tzinfo=now.tzinfo)
    return value


def _attempt_incomplete_stale(group: ImageProductionAbGroup, attempt: ImageProductionAbAttempt) -> bool:
    """业务函数：处理 _attempt_incomplete_stale 对应的业务流程、校验或数据转换。"""
    now = bj_now()
    timestamps = [
        _normalize_datetime_for_compare(value, now)
        for value in (group.updated_at, group.created_at, attempt.updated_at, attempt.created_at)
    ]
    latest = max((value for value in timestamps if value is not None), default=None)
    return latest is not None and now - latest >= INCOMPLETE_ATTEMPT_STALE_AFTER


def _existing_group_matches_payload(db: Session, existing: ImageProductionAbGroup, payload: dict[str, Any]) -> bool:
    """业务函数：处理 _existing_group_matches_payload 对应的业务流程、校验或数据转换。"""
    payload = _normalized_group_payload(payload)
    snapshot = _normalized_group_payload(existing.prompt_snapshot_json or {})
    if _canonical_request_payload(payload) != _canonical_request_payload(snapshot):
        return False

    requested_strategy_ids = list(payload.get("strategy_ids") or [])
    snapshot_strategy_ids = list(snapshot.get("strategy_ids") or [])
    if requested_strategy_ids != snapshot_strategy_ids:
        return False

    attempts = (
        db.query(ImageProductionAbAttempt)
        .filter_by(group_id=existing.id)
        .order_by(ImageProductionAbAttempt.created_at.asc(), ImageProductionAbAttempt.id.asc())
        .all()
    )
    if attempts and [attempt.strategy_id for attempt in attempts] != requested_strategy_ids:
        return False

    requested_strategy_versions = payload.get("strategy_versions")
    snapshot_strategy_versions = snapshot.get("strategy_versions")
    if requested_strategy_versions is not None or snapshot_strategy_versions is not None:
        if list(requested_strategy_versions or []) != list(snapshot_strategy_versions or []):
            return False

    if attempts and requested_strategy_versions is not None:
        if [attempt.strategy_version for attempt in attempts] != list(requested_strategy_versions):
            return False

    return True


def _reconcile_incomplete_existing_group(db: Session, group: ImageProductionAbGroup) -> None:
    """业务函数：处理 _reconcile_incomplete_existing_group 对应的业务流程、校验或数据转换。"""
    if _group_has_decision(group):
        return
    attempts = _attempt_rows(db, group.id)
    changed = False
    failed_incomplete = False
    if not any(not attempt.task_id and attempt.status in INCOMPLETE_ATTEMPT_STATUSES for attempt in attempts):
        return

    for index, attempt in enumerate(attempts):
        if attempt.task_id or attempt.status not in INCOMPLETE_ATTEMPT_STATUSES:
            continue
        task = (
            db.query(ImageCreationTask)
            .filter_by(
                idempotency_key=_attempt_key_for_existing_attempt(group, index, attempt),
                ab_test_group_id=group.id,
            )
            .first()
        )
        if task:
            attempt.task_id = task.id
            attempt.model_id = task.model_id
            attempt.status = "creating" if task.status in {"admission_pending", "queued", "running"} else task.status
            attempt.metrics_snapshot_json = {
                **(attempt.metrics_snapshot_json or {}),
                "estimated_cost": task.estimated_cost_json or {},
            }
            changed = True
            continue

        if not _attempt_incomplete_stale(group, attempt):
            continue

        attempt.status = "failed"
        attempt.metrics_snapshot_json = {
            **(attempt.metrics_snapshot_json or {}),
            "error_code": "IMAGE_AB_TEST_ATTEMPT_INCOMPLETE",
            "error": "A/B attempt did not finish creating an image task.",
        }
        changed = True
        failed_incomplete = True

    if failed_incomplete:
        group.status = "partial_failed" if any(attempt.task_id for attempt in attempts) else "failed"
    if changed:
        db.commit()
        db.refresh(group)


def _existing_group_for_key(
    db: Session,
    idempotency_key: str | None,
    request_hash: str | None,
    user_id: str | None,
    payload: dict[str, Any] | None = None,
) -> ImageProductionAbGroup | None:
    """业务函数：处理 _existing_group_for_key 对应的业务流程、校验或数据转换。"""
    if not idempotency_key:
        return None
    existing = db.query(ImageProductionAbGroup).filter_by(idempotency_key=idempotency_key).first()
    if not existing:
        return None
    user_matches = existing.user_id == user_id if user_id is not None else existing.user_id is None
    if not user_matches:
        raise _idempotency_conflict()
    if existing.source_request_hash != request_hash:
        raise _idempotency_conflict(existing)
    if payload is not None and not _existing_group_matches_payload(db, existing, payload):
        raise _idempotency_conflict(existing)
    _reconcile_incomplete_existing_group(db, existing)
    return existing


def _http_error_code(exc: HTTPException) -> str | None:
    """业务函数：处理 _http_error_code 对应的业务流程、校验或数据转换。"""
    if isinstance(exc.detail, dict):
        return exc.detail.get("error_code")
    return None


def _post_persist_failed_task(db: Session, idempotency_key: str | None, exc: HTTPException) -> ImageCreationTask | None:
    """业务函数：处理 _post_persist_failed_task 对应的业务流程、校验或数据转换。"""
    if _http_error_code(exc) != "PIXELLE_IMAGE_SUBMIT_FAILED" or not idempotency_key:
        return None
    task = db.query(ImageCreationTask).filter(ImageCreationTask.idempotency_key == idempotency_key).first()
    if task and task.status == "failed":
        return task
    return None


def _stored_preview_snapshot(db: Session, request_hash: str, user_id: str | None) -> dict[str, Any] | None:
    """业务函数：处理 _stored_preview_snapshot 对应的业务流程、校验或数据转换。"""
    request_hash_expr = ProductionAuditEvent.payload_json["request_hash"].as_string()
    rows = (
        db.query(ProductionAuditEvent)
        .filter(ProductionAuditEvent.event_type == "image_ab.preview")
        .filter(request_hash_expr == request_hash)
        .order_by(ProductionAuditEvent.created_at.desc(), ProductionAuditEvent.id.desc())
        .limit(50)
        .all()
    )
    for row in rows:
        payload = row.payload_json or {}
        if payload.get("request_hash") != request_hash:
            continue
        if user_id is not None and payload.get("user_id") != user_id:
            continue
        if user_id is None and payload.get("user_id") is not None:
            continue
        return payload
    return None


def _ensure_ab_cost_confirmation(payload: dict[str, Any], total_cost_estimate: dict[str, Any] | None) -> None:
    """业务函数：处理 _ensure_ab_cost_confirmation 对应的业务流程、校验或数据转换。"""
    if not total_cost_estimate or not total_cost_estimate.get("requires_confirmation") or payload.get("cost_confirmation"):
        return
    raise image_error(
        409,
        "IMAGE_AB_TEST_COST_CONFIRMATION_REQUIRED",
        "A/B comparison cost requires confirmation.",
        "Confirm the A/B group cost before creating tasks.",
        retryable=False,
        details={"total_cost_estimate": total_cost_estimate},
    )


def _preview_expired(value: Any) -> bool:
    """业务函数：处理 _preview_expired 对应的业务流程、校验或数据转换。"""
    if not value:
        return False
    try:
        expires_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return True
    now = bj_now()
    if expires_at.tzinfo is not None and now.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=None)
    if expires_at.tzinfo is None and now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    return expires_at <= now


def _strategy_version_matches(preview_version: Any, expected_version: Any) -> bool:
    """业务函数：处理 _strategy_version_matches 对应的业务流程、校验或数据转换。"""
    try:
        return int(preview_version) == int(expected_version)
    except (TypeError, ValueError):
        return False


def _snapshot_total_cost_matches(previews: list[dict[str, Any]], snapshot_total_cost: Any) -> bool:
    """业务函数：处理 _snapshot_total_cost_matches 对应的业务流程、校验或数据转换。"""
    if not isinstance(snapshot_total_cost, dict):
        return False
    try:
        return _total_cost(previews) == snapshot_total_cost
    except (TypeError, ValueError, KeyError):
        return False


def _validate_stored_preview_snapshot(
    payload: dict[str, Any],
    strategies: list[ImageProductionStrategy],
    snapshot: dict[str, Any] | None,
    expected_hash: str | None,
    user_id: str | None,
) -> dict[str, Any]:
    """业务函数：处理 _validate_stored_preview_snapshot 对应的业务流程、校验或数据转换。"""
    if not expected_hash or not snapshot:
        raise _preview_drift()
    strategy_ids = [strategy.id for strategy in strategies]
    strategy_versions = [strategy.version for strategy in strategies]
    preview_hashes = list(snapshot.get("preview_hashes") or [])
    snapshot_user_id = snapshot.get("user_id")
    if snapshot_user_id and user_id and snapshot_user_id != user_id:
        raise _preview_drift()
    if snapshot.get("request_hash") != expected_hash:
        raise _preview_drift()
    if snapshot.get("canonical_payload") != _canonical_request_payload(payload):
        raise _preview_drift()
    if snapshot.get("strategy_ids") != strategy_ids or snapshot.get("strategy_versions") != strategy_versions:
        raise _preview_drift()
    if expected_hash != _ab_request_hash(payload, strategies, preview_hashes):
        raise _preview_drift()
    previews = snapshot.get("previews")
    if not isinstance(previews, list) or len(previews) != len(strategies):
        raise _preview_drift()
    if len(preview_hashes) != len(previews):
        raise _preview_drift()
    for index, preview in enumerate(previews):
        if not isinstance(preview, dict):
            raise _preview_drift()
        if not _valid_preview_hash(preview_hashes[index]):
            raise _preview_drift()
        if preview.get("request_hash") != preview_hashes[index]:
            raise _preview_drift()
        if preview.get("strategy_id") != strategy_ids[index]:
            raise _preview_drift()
        if not _strategy_version_matches(preview.get("strategy_version"), strategy_versions[index]):
            raise _preview_drift()
        if _preview_expired(preview.get("expires_at")):
            raise _preview_drift()
    if not _snapshot_total_cost_matches(previews, snapshot.get("total_cost_estimate")):
        raise _preview_drift()
    return snapshot


async def create_ab_group(db: Session, payload: dict[str, Any], user_id: str | None = None) -> ImageProductionAbGroup:
    """业务函数：处理 create_ab_group 对应的业务流程、校验或数据转换。"""
    payload = _normalized_group_payload(payload)
    expected_hash = payload.get("preview_request_hash")
    idempotency_key = payload.get("idempotency_key")
    existing = _existing_group_for_key(db, idempotency_key, expected_hash, user_id, payload)
    if existing:
        return existing

    strategies = _strategy_rows(db, list(payload.get("strategy_ids") or []))
    _validate_stored_preview_snapshot(
        payload,
        strategies,
        _stored_preview_snapshot(db, expected_hash, user_id) if expected_hash else None,
        expected_hash,
        user_id,
    )
    preview = _ensure_preview_matches(db, payload, user_id=user_id, strategies=strategies)

    _ensure_ab_cost_confirmation(payload, preview["total_cost_estimate"])
    if (preview.get("total_cost_estimate") or {}).get("cost_limit_exceeded"):
        raise image_error(
            409,
            "IMAGE_AB_TEST_COST_LIMIT_EXCEEDED",
            "A/B comparison exceeds the configured group cost limit.",
            "Reduce count, choose cheaper strategies, or adjust policy.",
            retryable=False,
            details={"total_cost_estimate": preview["total_cost_estimate"]},
        )

    group = ImageProductionAbGroup(
        user_id=user_id,
        idempotency_key=idempotency_key,
        source_request_hash=expected_hash,
        prompt_snapshot_json=dict(payload),
        cost_confirmation_json={
            "confirmed": bool(payload.get("cost_confirmation")),
            "total_cost_estimate": preview["total_cost_estimate"],
        },
        status="running",
    )
    db.add(group)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        existing = _existing_group_for_key(db, idempotency_key, expected_hash, user_id, payload)
        if existing:
            return existing
        raise exc

    attempts: list[ImageProductionAbAttempt] = []
    for strategy in strategies:
        attempt = ImageProductionAbAttempt(
            group_id=group.id,
            strategy_id=strategy.id,
            strategy_version=strategy.version,
            model_id=strategy.default_model_id,
            status="creating",
            metrics_snapshot_json={},
        )
        db.add(attempt)
        db.flush()
        attempts.append(attempt)

    db.commit()
    db.refresh(group)

    successes = 0
    failures = 0
    for index, strategy in enumerate(strategies):
        attempt = attempts[index]
        attempt_preview = preview["previews"][index]
        selection_preview_request_hash = attempt_preview.get("request_hash")

        attempt_payload = _payload_for_strategy(payload, strategy)
        if not attempt_payload.get("destination_role"):
            attempt_payload["destination_role"] = strategy.destination_role
        attempt_payload["ab_test_group_id"] = group.id
        attempt_payload["user_id"] = user_id
        attempt_payload["idempotency_key"] = _attempt_key(payload, group, index, strategy)
        attempt_payload["cost_confirmation"] = bool(payload.get("cost_confirmation"))
        attempt_payload["selection_preview_request_hash"] = selection_preview_request_hash
        if attempt_preview.get("selection_preview_id"):
            attempt_payload["selection_preview_id"] = attempt_preview["selection_preview_id"]
        ab_attempt_idempotency_key = attempt_payload["idempotency_key"]
        ab_attempt_request_hash = None
        try:
            hash_payload = dict(attempt_payload)
            _apply_strategy_defaults(hash_payload, strategy)
            _resolve_source_asset(db, hash_payload)
            _resolve_reference_images(db, hash_payload)
            ab_attempt_request_hash = normalized_request_hash(hash_payload)
            attempt.metrics_snapshot_json = {
                "selection_preview_request_hash": selection_preview_request_hash,
                "ab_attempt_request_hash": ab_attempt_request_hash,
                "ab_attempt_idempotency_key": ab_attempt_idempotency_key,
            }
            db.flush()
            task = await create_image_task(db, attempt_payload)
            attempt.task_id = task.id
            attempt.model_id = task.model_id
            attempt.status = "creating" if task.status in {"admission_pending", "queued", "running"} else task.status
            attempt.metrics_snapshot_json = {
                "estimated_cost": task.estimated_cost_json or {},
                "selection_preview_request_hash": selection_preview_request_hash,
                "ab_attempt_request_hash": ab_attempt_request_hash,
                "ab_attempt_idempotency_key": ab_attempt_idempotency_key,
            }
            successes += 1
            db.commit()
        except HTTPException as exc:
            failed_task = _post_persist_failed_task(db, attempt_payload.get("idempotency_key"), exc)
            if failed_task:
                attempt.task_id = failed_task.id
                attempt.model_id = failed_task.model_id
                attempt.status = "failed"
                attempt.metrics_snapshot_json = {
                    "estimated_cost": failed_task.estimated_cost_json or {},
                    "selection_preview_request_hash": selection_preview_request_hash,
                    "ab_attempt_request_hash": ab_attempt_request_hash,
                    "ab_attempt_idempotency_key": ab_attempt_idempotency_key,
                    "error_code": _http_error_code(exc),
                    "error": _safe_ab_error_message(failed_task.error_message or str(exc)),
                }
            else:
                attempt.status = "failed"
                attempt.metrics_snapshot_json = {
                    "selection_preview_request_hash": selection_preview_request_hash,
                    "ab_attempt_request_hash": ab_attempt_request_hash,
                    "ab_attempt_idempotency_key": ab_attempt_idempotency_key,
                    "error_code": _http_error_code(exc),
                    "error": _safe_ab_error_message(str(exc.detail) if exc.detail else str(exc)),
                }
            failures += 1
            db.commit()
            continue
        except SQLAlchemyError:
            db.rollback()
            raise
        except RuntimeError as exc:
            attempt.status = "failed"
            attempt.metrics_snapshot_json = {
                "selection_preview_request_hash": selection_preview_request_hash,
                "ab_attempt_request_hash": ab_attempt_request_hash,
                "ab_attempt_idempotency_key": ab_attempt_idempotency_key,
                "error": _safe_ab_error_message(exc),
            }
            failures += 1
            db.commit()

    if failures and successes:
        group.status = "partial_failed"
        _record(
            db,
            "image_ab.partial_failed",
            {
                **_group_audit_payload(db, group),
                "failure_count": failures,
                "success_count": successes,
            },
        )
    elif failures:
        group.status = "failed"
    else:
        group.status = "running"
    _record(db, "image_ab.create", _group_audit_payload(db, group))
    db.commit()
    db.refresh(group)
    return group


def get_ab_group(db: Session, group_id: str, user_id: str | None = None) -> ImageProductionAbGroup:
    """业务函数：处理 get_ab_group 对应的业务流程、校验或数据转换。"""
    group = db.query(ImageProductionAbGroup).filter_by(id=group_id).first()
    if not group or group.user_id != user_id:
        raise image_error(
            404,
            "IMAGE_AB_TEST_GROUP_NOT_FOUND",
            "A/B group was not found.",
            "Reload A/B comparisons.",
            retryable=False,
            affected_ids=[group_id],
        )
    return group


def _attempt_rows(db: Session, group_id: str) -> list[ImageProductionAbAttempt]:
    """业务函数：处理 _attempt_rows 对应的业务流程、校验或数据转换。"""
    return (
        db.query(ImageProductionAbAttempt)
        .filter_by(group_id=group_id)
        .order_by(ImageProductionAbAttempt.created_at.asc(), ImageProductionAbAttempt.id.asc())
        .all()
    )


def _assert_attempts_terminal_for_decision(db: Session, group: ImageProductionAbGroup) -> None:
    """业务函数：处理 _assert_attempts_terminal_for_decision 对应的业务流程、校验或数据转换。"""
    attempts = _attempt_rows(db, group.id)
    statuses = {attempt.status for attempt in attempts}
    if attempts and statuses.issubset(TERMINAL_TASK_STATUSES):
        return
    raise image_error(
        409,
        "IMAGE_AB_TEST_ATTEMPT_NOT_READY",
        "A/B group attempts are not ready for a final decision.",
        "Wait for all attempts to finish, then refresh the group before deciding.",
        retryable=True,
        affected_ids=[group.id],
    )


def _approved_assets(db: Session, attempt: ImageProductionAbAttempt) -> list[ImageCreationAsset]:
    """业务函数：处理 _approved_assets 对应的业务流程、校验或数据转换。"""
    if not attempt.task_id:
        return []
    return (
        db.query(ImageCreationAsset)
        .filter(ImageCreationAsset.task_id == attempt.task_id)
        .filter(ImageCreationAsset.status == "approved")
        .order_by(ImageCreationAsset.created_at.asc(), ImageCreationAsset.id.asc())
        .all()
    )


def _group_total_cost_estimate(group: ImageProductionAbGroup) -> dict[str, Any] | None:
    """业务函数：处理 _group_total_cost_estimate 对应的业务流程、校验或数据转换。"""
    cost_confirmation = group.cost_confirmation_json or {}
    if not isinstance(cost_confirmation, dict):
        return None
    total_cost = cost_confirmation.get("total_cost_estimate")
    return total_cost if isinstance(total_cost, dict) else None


def _attempt_audit_summary(db: Session, group_id: str) -> list[dict[str, Any]]:
    """业务函数：处理 _attempt_audit_summary 对应的业务流程、校验或数据转换。"""
    summaries = []
    for attempt in _attempt_rows(db, group_id):
        metrics = attempt.metrics_snapshot_json or {}
        summary = {
            "attempt_id": attempt.id,
            "status": attempt.status,
            "task_id": attempt.task_id,
            "strategy_id": attempt.strategy_id,
            "strategy_version": attempt.strategy_version,
            "model_id": attempt.model_id,
        }
        if metrics.get("error_code"):
            summary["error_code"] = metrics["error_code"]
        summaries.append(summary)
    return summaries


def _group_audit_payload(db: Session, group: ImageProductionAbGroup, *, status: str | None = None) -> dict[str, Any]:
    """业务函数：处理 _group_audit_payload 对应的业务流程、校验或数据转换。"""
    attempts = _attempt_audit_summary(db, group.id)
    payload: dict[str, Any] = {
        "group_id": group.id,
        "status": status or group.status,
        "strategy_count": len(attempts),
        "attempts": attempts,
    }
    total_cost = _group_total_cost_estimate(group)
    if total_cost is not None:
        payload["total_cost_estimate"] = total_cost
    return payload


def refresh_ab_group(db: Session, group_id: str, user_id: str | None = None) -> ImageProductionAbGroup:
    """业务函数：处理 refresh_ab_group 对应的业务流程、校验或数据转换。"""
    group = get_ab_group(db, group_id, user_id=user_id)
    attempts = _attempt_rows(db, group.id)
    for attempt in attempts:
        task = db.query(ImageCreationTask).filter_by(id=attempt.task_id).first() if attempt.task_id else None
        if not task:
            continue
        metric = refresh_image_strategy_metrics(db, attempt.strategy_id, attempt.strategy_version, task.model_id)
        existing_metrics = attempt.metrics_snapshot_json or {}
        attempt.status = task.status
        attempt.model_id = task.model_id
        attempt.metrics_snapshot_json = {
            **existing_metrics,
            "estimated_cost": task.estimated_cost_json or {},
            "metrics": strategy_metrics_payload(metric),
        }

    statuses = {attempt.status for attempt in attempts}
    next_status = None
    if not _group_has_decision(group) and statuses and statuses.issubset(TERMINAL_TASK_STATUSES):
        if statuses == {"completed"}:
            next_status = "completed"
        elif statuses == {"failed"}:
            next_status = "failed"
        else:
            next_status = "partial_failed"
    if next_status:
        (
            db.query(ImageProductionAbGroup)
            .filter(ImageProductionAbGroup.id == group.id)
            .filter(ImageProductionAbGroup.winner_attempt_id.is_(None))
            .filter(~ImageProductionAbGroup.status.in_(DECISION_STATUSES))
            .update({"status": next_status}, synchronize_session=False)
        )
    db.commit()
    db.refresh(group)
    return group


def recommend_ab_winner(db: Session, group_id: str, user_id: str | None = None) -> dict[str, Any]:
    """业务函数：处理 recommend_ab_winner 对应的业务流程、校验或数据转换。"""
    return ab_winner_recommendation_payload(db, group_id, user_id=user_id)


def _assert_no_decision(group: ImageProductionAbGroup) -> None:
    """业务函数：处理 _assert_no_decision 对应的业务流程、校验或数据转换。"""
    if _group_has_decision(group):
        raise image_error(
            409,
            "IMAGE_AB_TEST_WINNER_CONFLICT",
            "This A/B group already has a decision.",
            "Reload the group and review the recorded decision.",
            retryable=False,
            affected_ids=[group.id],
        )


def _ab_decision_evidence_snapshot(
    db: Session,
    group: ImageProductionAbGroup,
    winner_attempt_id: str | None,
    decision: dict[str, Any],
) -> dict[str, Any]:
    """业务函数：处理 _ab_decision_evidence_snapshot 对应的业务流程、校验或数据转换。"""
    attempts = []
    for attempt in _attempt_rows(db, group.id):
        task = db.query(ImageCreationTask).filter(ImageCreationTask.id == attempt.task_id).first() if attempt.task_id else None
        approved_assets = _approved_assets(db, attempt)
        attempts.append({
            "attempt_id": attempt.id,
            "task_id": attempt.task_id,
            "strategy_id": attempt.strategy_id,
            "strategy_version": attempt.strategy_version,
            "model_id": attempt.model_id,
            "status": attempt.status,
            "approved_asset_ready": bool(approved_assets),
            "approved_asset_ids": [asset.id for asset in approved_assets],
            "metrics": attempt.metrics_snapshot_json or {},
            "task_status": task.status if task else None,
            "estimated_cost": task.estimated_cost_json if task else {},
        })
    return {
        "decision": "winner" if winner_attempt_id else "no_winner",
        "winner_attempt_id": winner_attempt_id,
        "reason": decision.get("reason") or "",
        "notes": decision.get("notes") or "",
        "decided_at": bj_now().isoformat(),
        "attempts": attempts,
    }


def adopt_ab_winner(
    db: Session,
    group_id: str,
    attempt_id: str,
    decision: dict[str, Any],
    user_id: str | None = None,
) -> ImageProductionAbGroup:
    """业务函数：处理 adopt_ab_winner 对应的业务流程、校验或数据转换。"""
    group = get_ab_group(db, group_id, user_id=user_id)
    _assert_no_decision(group)
    attempt = db.query(ImageProductionAbAttempt).filter_by(id=attempt_id, group_id=group.id).first()
    if not attempt:
        raise image_error(
            404,
            "IMAGE_AB_TEST_ATTEMPT_NOT_FOUND",
            "A/B attempt was not found.",
            "Reload the A/B group.",
            retryable=False,
            affected_ids=[attempt_id],
        )
    approved_assets = _approved_assets(db, attempt)
    if not approved_assets:
        raise image_error(
            409,
            "IMAGE_AB_TEST_ATTEMPT_NOT_READY",
            "Winner attempt must have at least one approved image asset.",
            "Approve an image asset before choosing the winner.",
            retryable=False,
            affected_ids=[attempt_id],
        )

    snapshot = _ab_decision_evidence_snapshot(db, group, attempt.id, decision)
    decision_json = {
        "reason": decision.get("reason") or "",
        "notes": decision.get("notes") or "",
        "winner_attempt_id": attempt.id,
        "winner_asset_ids": [asset.id for asset in approved_assets],
        "evidence_snapshot": snapshot,
    }
    rowcount = (
        db.query(ImageProductionAbGroup)
        .filter(ImageProductionAbGroup.id == group.id)
        .filter(ImageProductionAbGroup.winner_attempt_id.is_(None))
        .filter(~ImageProductionAbGroup.status.in_(DECISION_STATUSES))
        .update(
            {
                "winner_attempt_id": attempt.id,
                "status": "winner_selected",
                "decision_json": decision_json,
            },
            synchronize_session=False,
        )
    )
    if rowcount == 0:
        db.rollback()
        raise image_error(
            409,
            "IMAGE_AB_TEST_WINNER_CONFLICT",
            "This A/B group already has a decision.",
            "Reload the group and review the recorded decision.",
            retryable=False,
            affected_ids=[group.id],
        )
    attempt.human_decision_json = {"selected": True, **decision_json}
    _record(
        db,
        "image_ab.winner",
        {
            **_group_audit_payload(db, group, status="winner_selected"),
            "winner_attempt_id": attempt.id,
            "winner_asset_ids": [asset.id for asset in approved_assets],
            "decision_summary": {
                "reason": decision_json["reason"],
                "notes": decision_json["notes"],
            },
        },
    )
    db.commit()
    db.refresh(group)
    return group


def mark_ab_no_winner(
    db: Session,
    group_id: str,
    decision: dict[str, Any],
    user_id: str | None = None,
) -> ImageProductionAbGroup:
    """业务函数：处理 mark_ab_no_winner 对应的业务流程、校验或数据转换。"""
    group = get_ab_group(db, group_id, user_id=user_id)
    _assert_no_decision(group)
    _assert_attempts_terminal_for_decision(db, group)
    snapshot = _ab_decision_evidence_snapshot(db, group, None, decision)
    decision_json = {
        "reason": decision.get("reason") or "",
        "notes": decision.get("notes") or "",
        "evidence_snapshot": snapshot,
    }
    rowcount = (
        db.query(ImageProductionAbGroup)
        .filter(ImageProductionAbGroup.id == group.id)
        .filter(ImageProductionAbGroup.winner_attempt_id.is_(None))
        .filter(~ImageProductionAbGroup.status.in_(DECISION_STATUSES))
        .update(
            {
                "winner_attempt_id": None,
                "status": "no_winner",
                "decision_json": decision_json,
            },
            synchronize_session=False,
        )
    )
    if rowcount == 0:
        db.rollback()
        raise image_error(
            409,
            "IMAGE_AB_TEST_WINNER_CONFLICT",
            "This A/B group already has a decision.",
            "Reload the group and review the recorded decision.",
            retryable=False,
            affected_ids=[group.id],
        )
    _record(
        db,
        "image_ab.no_winner",
        {
            **_group_audit_payload(db, group, status="no_winner"),
            "decision_summary": {
                "reason": decision_json["reason"],
                "notes": decision_json["notes"],
            },
        },
    )
    db.commit()
    db.refresh(group)
    return group


def serialize_ab_group(db: Session, group: ImageProductionAbGroup) -> dict[str, Any]:
    """业务函数：处理 serialize_ab_group 对应的业务流程、校验或数据转换。"""
    attempts = []
    for attempt in _attempt_rows(db, group.id):
        task = db.query(ImageCreationTask).filter_by(id=attempt.task_id).first() if attempt.task_id else None
        approved_assets = _approved_assets(db, attempt)
        attempts.append({
            "id": attempt.id,
            "group_id": attempt.group_id,
            "task_id": attempt.task_id,
            "strategy_id": attempt.strategy_id,
            "strategy_version": attempt.strategy_version,
            "model_id": attempt.model_id,
            "status": attempt.status,
            "metrics_snapshot": attempt.metrics_snapshot_json or {},
            "human_decision": attempt.human_decision_json or {},
            "task_status": task.status if task else None,
            "approved_asset_ready": bool(approved_assets),
            "approved_asset_ids": [asset.id for asset in approved_assets],
            "task": task_payload(task) if task else None,
            "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
            "updated_at": attempt.updated_at.isoformat() if attempt.updated_at else None,
        })
    return {
        "id": group.id,
        "user_id": group.user_id,
        "idempotency_key": group.idempotency_key,
        "source_request_hash": group.source_request_hash,
        "prompt_snapshot": group.prompt_snapshot_json or {},
        "cost_confirmation": group.cost_confirmation_json or {},
        "winner_attempt_id": group.winner_attempt_id,
        "decision": group.decision_json or {},
        "status": group.status,
        "attempts": attempts,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "updated_at": group.updated_at.isoformat() if group.updated_at else None,
    }
