"""图片生成业务域模块。

图片生成业务域，负责图片任务创建、策略选择、审核门禁和生成资产入库。本文件负责 image_production_policy_runtime 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.models.image_production import ImageCreationTask, ImageProductionPolicyVersion, ImageProductionStrategy


DEFAULT_COST_POLICY = {
    "unit_cost": 1.0,
    "currency": "CNY",
    "confirmation_threshold": 1.0,
    "latency_seconds_per_image": 10,
    "ab_max_group_cost": None,
}
DEFAULT_CAPACITY_POLICY = {
    "mode": "preview_only",
    "max_concurrent": 1,
    "average_task_seconds": 30,
    "queue_when_full": False,
}
DEFAULT_REVIEW_POLICY = {
    "manual_required_for": ["image_to_video_input"],
    "ai_required_for": [],
}


def _policy_snapshot(
    db: Session,
    policy_id: str | None,
    policy_type: str,
    default_snapshot: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    """业务函数：处理 _policy_snapshot 对应的业务流程、校验或数据转换。"""
    if not policy_id:
        return dict(default_snapshot), None
    row = (
        db.query(ImageProductionPolicyVersion)
        .filter(ImageProductionPolicyVersion.id == policy_id)
        .filter(ImageProductionPolicyVersion.policy_type == policy_type)
        .first()
    )
    if not row:
        return dict(default_snapshot), None
    snapshot = dict(default_snapshot)
    snapshot.update(row.snapshot_json or {})
    return snapshot, row.id


def _count_images(payload: dict[str, Any]) -> int:
    """业务函数：处理 _count_images 对应的业务流程、校验或数据转换。"""
    try:
        return max(1, int(payload.get("count") or 1))
    except (TypeError, ValueError):
        return 1


def estimate_image_cost(
    db: Session,
    payload: dict[str, Any],
    strategy: ImageProductionStrategy | None,
    model_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """业务函数：处理 estimate_image_cost 对应的业务流程、校验或数据转换。"""
    policy, policy_id = _policy_snapshot(
        db,
        strategy.cost_policy_version_id if strategy else None,
        "cost",
        DEFAULT_COST_POLICY,
    )
    model_cost = ((model_config or {}).get("config") or {}).get("cost_profile") or {}
    unit_cost = float(model_cost.get("unit_cost", policy.get("unit_cost", 1.0)))
    currency = str(model_cost.get("currency", policy.get("currency", "CNY")))
    count = _count_images(payload)
    amount = round(unit_cost * count, 4)
    threshold = float(policy.get("confirmation_threshold", 1.0))
    latency = int(policy.get("latency_seconds_per_image", 10)) * count
    result = {
        "amount": amount,
        "currency": currency,
        "estimate_source": "policy",
        "requires_confirmation": amount > threshold,
        "confirmation_threshold": threshold,
        "units": {"images": count, "unit_cost": unit_cost},
        "policy_version_id": policy_id,
        "time_estimate": {"estimated_seconds": latency, "estimate_source": "policy"},
    }
    ab_max_group_cost = policy.get("ab_max_group_cost")
    if isinstance(ab_max_group_cost, str):
        ab_max_group_cost = ab_max_group_cost.strip()
    if ab_max_group_cost not in (None, ""):
        result["ab_max_group_cost"] = float(ab_max_group_cost)
    return result


def preview_image_capacity(
    db: Session,
    strategy: ImageProductionStrategy | None,
    model_id: str | None,
) -> dict[str, Any]:
    """业务函数：处理 preview_image_capacity 对应的业务流程、校验或数据转换。"""
    policy, policy_id = _policy_snapshot(
        db,
        strategy.capacity_policy_version_id if strategy else None,
        "capacity",
        DEFAULT_CAPACITY_POLICY,
    )
    max_concurrent = max(1, int(policy.get("max_concurrent") or 1))
    average_task_seconds = max(1, int(policy.get("average_task_seconds") or 30))
    query = db.query(ImageCreationTask).filter(ImageCreationTask.status.in_(["queued", "running"]))
    if strategy:
        query = query.filter(ImageCreationTask.strategy_id == strategy.id)
    if model_id:
        query = query.filter(ImageCreationTask.model_id == model_id)
    active_count = query.filter(or_(
        ImageCreationTask.status == "running",
        and_(
            ImageCreationTask.status == "queued",
            ImageCreationTask.capacity_lease_id.isnot(None),
        ),
    )).count()
    queued_count = query.filter(
        ImageCreationTask.status == "queued",
        ImageCreationTask.queue_job_id.isnot(None),
        ImageCreationTask.capacity_lease_id.is_(None),
    ).count()
    policy_mode = policy.get("mode", "preview_only")
    if policy_mode == "preview_only":
        return {
            "mode": policy_mode,
            "status": "available",
            "max_concurrent": max_concurrent,
            "active_count": active_count,
            "queued_count": queued_count,
            "queue_depth": queued_count,
            "estimated_wait_seconds": 0,
            "admission_action": "submit_now",
            "policy_version_id": policy_id,
        }
    full = active_count >= max_concurrent
    queue_when_full = bool(policy.get("queue_when_full"))
    status = "available"
    admission_action = "submit_now"
    queue_depth = queued_count
    if full and queue_when_full:
        status = "queued"
        admission_action = "queue"
        queue_depth = queued_count + 1
    elif full:
        status = "blocked"
        admission_action = "block"
        queue_depth = queued_count
    return {
        "mode": policy_mode,
        "status": status,
        "max_concurrent": max_concurrent,
        "active_count": active_count,
        "queued_count": queued_count,
        "queue_depth": queue_depth,
        "estimated_wait_seconds": queue_depth * average_task_seconds if status in {"queued", "blocked"} else 0,
        "admission_action": admission_action,
        "policy_version_id": policy_id,
    }


def preview_review_gate(
    db: Session,
    strategy: ImageProductionStrategy | None,
    destination_role: str | None,
) -> dict[str, Any]:
    """业务函数：处理 preview_review_gate 对应的业务流程、校验或数据转换。"""
    policy, policy_id = _policy_snapshot(
        db,
        strategy.review_policy_version_id if strategy else None,
        "review",
        DEFAULT_REVIEW_POLICY,
    )
    role = destination_role or (strategy.destination_role if strategy else "")
    manual_required = role in set(policy.get("manual_required_for") or [])
    ai_required = role in set(policy.get("ai_required_for") or [])
    required = manual_required or ai_required
    if manual_required:
        status = "manual_review_pending"
    elif ai_required:
        status = "ai_review_pending"
    else:
        status = "not_required"
    return {
        "required": required,
        "manual_required": manual_required,
        "ai_required": ai_required,
        "status": status,
        "policy_version_id": policy_id,
        "reason": f"{role} requires review before video promotion" if required else "No review gate required for this role",
    }
