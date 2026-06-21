"""图片生成业务域模块。

图片生成业务域，负责图片任务创建、策略选择、审核门禁和生成资产入库。本文件负责 image_production_metrics_service 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db.models.image_production import (
    ImageCreationAsset,
    ImageCreationReviewRecord,
    ImageCreationTask,
    ImageProductionCostEvent,
    ImageProductionMetric,
)


SUCCESS_TASK_STATUSES = {"completed", "completed_with_warnings"}


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _latency_seconds(task: ImageCreationTask) -> float | None:
    if task.created_at and task.completed_at:
        return max(0.0, (task.completed_at - task.created_at).total_seconds())
    return None


def _actual_costs(db: Session, task_ids: list[str]) -> tuple[list[float], str]:
    if not task_ids:
        return [], "CNY"

    rows = (
        db.query(ImageProductionCostEvent)
        .filter(ImageProductionCostEvent.task_id.in_(task_ids))
        .filter(ImageProductionCostEvent.event_type == "actual")
        .all()
    )
    latest_by_task: dict[str, ImageProductionCostEvent] = {}
    for row in rows:
        current = latest_by_task.get(row.task_id)
        row_key = (row.created_at, row.id)
        current_key = (current.created_at, current.id) if current else None
        if current_key is None or row_key > current_key:
            latest_by_task[row.task_id] = row

    selected = sorted(latest_by_task.values(), key=lambda row: (row.created_at, row.id))
    costs = [float(row.actual_cost or 0.0) for row in selected]
    currency = selected[0].currency if selected else "CNY"
    return costs, currency


def _is_human_review(review: ImageCreationReviewRecord) -> bool:
    return review.review_type in {"human", "manual"} or review.reviewer_type == "human"


def _is_approved_review(review: ImageCreationReviewRecord) -> bool:
    return review.action == "approve" or review.status == "approved"


def refresh_image_strategy_metrics(
    db: Session,
    strategy_id: str,
    strategy_version: int,
    model_id: str | None,
) -> ImageProductionMetric:
    task_query = (
        db.query(ImageCreationTask)
        .filter(ImageCreationTask.strategy_id == strategy_id)
        .filter(ImageCreationTask.strategy_version == strategy_version)
    )
    if model_id is None:
        task_query = task_query.filter(ImageCreationTask.model_id.is_(None))
    else:
        task_query = task_query.filter(ImageCreationTask.model_id == model_id)

    tasks = task_query.all()
    task_ids = [task.id for task in tasks]
    assets = (
        db.query(ImageCreationAsset).filter(ImageCreationAsset.task_id.in_(task_ids)).all()
        if task_ids
        else []
    )
    reviews = (
        db.query(ImageCreationReviewRecord)
        .filter(ImageCreationReviewRecord.task_id.in_(task_ids))
        .filter(ImageCreationReviewRecord.is_latest_asset_review.is_(True))
        .all()
        if task_ids
        else []
    )
    costs, currency = _actual_costs(db, task_ids)
    latencies = [value for value in (_latency_seconds(task) for task in tasks) if value is not None]

    metric_query = (
        db.query(ImageProductionMetric)
        .filter(ImageProductionMetric.strategy_id == strategy_id)
        .filter(ImageProductionMetric.strategy_version == strategy_version)
    )
    if model_id is None:
        metric_query = metric_query.filter(ImageProductionMetric.model_id.is_(None))
    else:
        metric_query = metric_query.filter(ImageProductionMetric.model_id == model_id)

    metric = metric_query.first()
    if metric is None:
        metric = ImageProductionMetric(
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            model_id=model_id,
        )
        db.add(metric)

    metric.attempt_count = len(tasks)
    metric.success_count = len([task for task in tasks if task.status in SUCCESS_TASK_STATUSES])
    metric.failure_count = len([task for task in tasks if task.status == "failed"])
    metric.ai_pass_count = len({asset.task_id for asset in assets if asset.audit_status == "approved"})
    metric.human_pass_count = len(
        {
            review.task_id
            for review in reviews
            if _is_human_review(review) and _is_approved_review(review)
        }
    )
    metric.repaint_count = len(
        {
            asset.task_id
            for asset in assets
            if asset.status in {"repaint", "regenerating"} or asset.source_asset_id
        }
    )
    metric.average_latency_seconds = _avg(latencies)
    metric.average_cost_amount = _avg(costs)
    metric.currency = currency
    metric.updated_at = bj_now()
    db.flush()
    db.refresh(metric)
    return metric


def _weighted_average(metrics: list[ImageProductionMetric], field: str) -> float:
    total_attempts = sum(max(metric.attempt_count or 0, 0) for metric in metrics)
    if total_attempts == 0:
        return 0
    total = sum(float(getattr(metric, field) or 0) * max(metric.attempt_count or 0, 0) for metric in metrics)
    return round(total / total_attempts, 4)


def aggregate_strategy_metrics_payload(metrics: list[ImageProductionMetric]) -> dict[str, Any]:
    attempt_count = sum(metric.attempt_count or 0 for metric in metrics)
    success_count = sum(metric.success_count or 0 for metric in metrics)
    failure_count = sum(metric.failure_count or 0 for metric in metrics)
    ai_pass_count = sum(metric.ai_pass_count or 0 for metric in metrics)
    human_pass_count = sum(metric.human_pass_count or 0 for metric in metrics)
    repaint_count = sum(metric.repaint_count or 0 for metric in metrics)
    currencies = {metric.currency for metric in metrics if metric.currency}
    updated_at = max((metric.updated_at for metric in metrics if metric.updated_at), default=None)
    attempts = max(attempt_count, 1)
    return {
        "attempt_count": attempt_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round(success_count / attempts, 4),
        "ai_pass_rate": round(ai_pass_count / attempts, 4),
        "human_pass_rate": round(human_pass_count / attempts, 4),
        "repaint_count": repaint_count,
        "average_latency_seconds": _weighted_average(metrics, "average_latency_seconds"),
        "average_cost_amount": _weighted_average(metrics, "average_cost_amount"),
        "currency": next(iter(currencies)) if len(currencies) == 1 else "MIXED" if currencies else "CNY",
        "low_sample": attempt_count < 5,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


def refresh_all_image_strategy_metrics(
    db: Session,
    strategy_id: str | None = None,
    strategy_version: int | None = None,
) -> dict[str, Any]:
    query = (
        db.query(
            ImageCreationTask.strategy_id,
            ImageCreationTask.strategy_version,
            ImageCreationTask.model_id,
        )
        .filter(ImageCreationTask.strategy_id.isnot(None))
        .filter(ImageCreationTask.strategy_version.isnot(None))
    )
    if strategy_id is not None:
        query = query.filter(ImageCreationTask.strategy_id == strategy_id)
    if strategy_version is not None:
        query = query.filter(ImageCreationTask.strategy_version == strategy_version)

    rows = (
        query.distinct()
        .order_by(
            ImageCreationTask.strategy_id.asc(),
            ImageCreationTask.strategy_version.asc(),
            ImageCreationTask.model_id.asc().nullsfirst(),
        )
        .all()
    )
    keys = [
        {
            "strategy_id": row.strategy_id,
            "strategy_version": row.strategy_version,
            "model_id": row.model_id,
        }
        for row in rows
    ]
    for key in keys:
        refresh_image_strategy_metrics(
            db,
            key["strategy_id"],
            key["strategy_version"],
            key["model_id"],
        )

    return {"refreshed_count": len(keys), "keys": keys}


def strategy_metrics_payload(metric: ImageProductionMetric | None) -> dict[str, Any]:
    if metric is None:
        return {
            "attempt_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "success_rate": 0,
            "ai_pass_rate": 0,
            "human_pass_rate": 0,
            "repaint_count": 0,
            "average_latency_seconds": 0,
            "average_cost_amount": 0,
            "currency": "CNY",
            "low_sample": True,
        }

    attempts = max(metric.attempt_count, 1)
    return {
        "attempt_count": metric.attempt_count,
        "success_count": metric.success_count,
        "failure_count": metric.failure_count,
        "success_rate": round(metric.success_count / attempts, 4),
        "ai_pass_rate": round(metric.ai_pass_count / attempts, 4),
        "human_pass_rate": round(metric.human_pass_count / attempts, 4),
        "repaint_count": metric.repaint_count,
        "average_latency_seconds": metric.average_latency_seconds,
        "average_cost_amount": metric.average_cost_amount,
        "currency": metric.currency,
        "low_sample": metric.attempt_count < 5,
        "updated_at": metric.updated_at.isoformat() if metric.updated_at else None,
    }
