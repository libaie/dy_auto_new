from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db_models import (
    ImageCreationAsset,
    ImageProductionAbAttempt,
    ImageProductionAbGroup,
    ImageProductionMetric,
    ImageProductionStrategy,
)
from app.services.image_creation_errors import image_error
from app.domains.image_generation.image_production_metrics_service import aggregate_strategy_metrics_payload


AB_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "completed_with_warnings"}
AB_RECOMMENDABLE_STATUSES = {"completed", "completed_with_warnings"}
AB_DECISION_STATUSES = {"winner_selected", "no_winner"}
LOW_SAMPLE_ATTEMPTS = 5
HIGH_CONFIDENCE_ATTEMPTS = 20
HIGH_FAILURE_RATE = 0.2
HIGH_REPAINT_RATE = 0.2


def _quality_score(metrics: dict[str, Any]) -> int:
    failure_rate = metrics["failure_count"] / max(metrics["attempt_count"], 1)
    repaint_rate = metrics["repaint_count"] / max(metrics["attempt_count"], 1)
    score = 100 - (failure_rate * 60) - (repaint_rate * 30)
    return max(0, min(100, round(score)))


def _recommendations(metrics: dict[str, Any], score: int) -> list[dict[str, str]]:
    attempt_count = metrics["attempt_count"]
    failure_rate = metrics["failure_count"] / max(attempt_count, 1)
    repaint_rate = metrics["repaint_count"] / max(attempt_count, 1)
    recommendations: list[dict[str, str]] = []

    if attempt_count < LOW_SAMPLE_ATTEMPTS:
        recommendations.append({
            "code": "LOW_SAMPLE",
            "severity": "info",
            "message": "Collect more strategy samples before changing automation.",
        })
    if failure_rate >= HIGH_FAILURE_RATE:
        recommendations.append({
            "code": "HIGH_FAILURE_RATE",
            "severity": "warning",
            "message": "Failure rate is above the strategy control threshold.",
        })
    if repaint_rate >= HIGH_REPAINT_RATE:
        recommendations.append({
            "code": "HIGH_REPAINT_RATE",
            "severity": "warning",
            "message": "Repaint rate is above the strategy control threshold.",
        })
    if not recommendations and score >= 85:
        recommendations.append({
            "code": "KEEP_STRATEGY",
            "severity": "success",
            "message": "Keep this strategy as the current default candidate.",
        })

    return recommendations


def _confidence(metrics: dict[str, Any]) -> str:
    attempt_count = metrics["attempt_count"]
    if attempt_count < LOW_SAMPLE_ATTEMPTS:
        return "low"
    if attempt_count < HIGH_CONFIDENCE_ATTEMPTS:
        return "medium"
    return "high"


def _status(metrics: dict[str, Any], score: int, recommendations: list[dict[str, str]]) -> str:
    codes = {item["code"] for item in recommendations}
    if metrics["low_sample"] or "HIGH_FAILURE_RATE" in codes or "HIGH_REPAINT_RATE" in codes or score < 70:
        return "cautious"
    if score >= 85:
        return "recommended"
    return "monitor"


def strategy_recommendation_payload(db: Session, strategy_id: str) -> dict[str, Any]:
    strategy = db.query(ImageProductionStrategy).filter(ImageProductionStrategy.id == strategy_id).first()
    if strategy is None:
        raise image_error(
            404,
            "IMAGE_STRATEGY_NOT_FOUND",
            "Image production strategy not found.",
            "Reload the strategy list.",
            retryable=False,
        )

    metric_rows = (
        db.query(ImageProductionMetric)
        .filter(ImageProductionMetric.strategy_id == strategy.id)
        .filter(ImageProductionMetric.strategy_version == strategy.version)
        .all()
    )
    metrics = aggregate_strategy_metrics_payload(metric_rows)
    score = _quality_score(metrics)
    recommendations = _recommendations(metrics, score)

    return {
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "metrics": metrics,
        "quality_score": score,
        "confidence": _confidence(metrics),
        "status": _status(metrics, score, recommendations),
        "recommendations": recommendations,
        "automatic_mutation_allowed": False,
    }


def _ab_attempt_rows(db: Session, group_id: str) -> list[ImageProductionAbAttempt]:
    return (
        db.query(ImageProductionAbAttempt)
        .filter_by(group_id=group_id)
        .order_by(ImageProductionAbAttempt.created_at.asc(), ImageProductionAbAttempt.id.asc())
        .all()
    )


def _approved_asset_ids(db: Session, attempt: ImageProductionAbAttempt) -> list[str]:
    if not attempt.task_id:
        return []
    rows = (
        db.query(ImageCreationAsset)
        .filter(ImageCreationAsset.task_id == attempt.task_id)
        .filter(ImageCreationAsset.status == "approved")
        .order_by(ImageCreationAsset.created_at.asc(), ImageCreationAsset.id.asc())
        .all()
    )
    return [row.id for row in rows]


def _metric_number(metrics: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = metrics.get(key)
        if value is None and isinstance(metrics.get("metrics"), dict):
            value = metrics["metrics"].get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _estimated_cost_amount(metrics: dict[str, Any]) -> float | None:
    estimated_cost = metrics.get("estimated_cost")
    if isinstance(estimated_cost, dict):
        try:
            return float(estimated_cost.get("amount"))
        except (TypeError, ValueError):
            return None
    return _metric_number(metrics, "cost_amount", "average_cost_amount")


def _ab_attempt_score(db: Session, attempt: ImageProductionAbAttempt) -> dict[str, Any]:
    metrics = attempt.metrics_snapshot_json or {}
    if not isinstance(metrics, dict):
        metrics = {}
    approved_asset_ids = _approved_asset_ids(db, attempt)
    approved_asset_ready = bool(approved_asset_ids)
    terminal = attempt.status in AB_TERMINAL_STATUSES
    recommendable = approved_asset_ready and attempt.status in AB_RECOMMENDABLE_STATUSES
    latency_seconds = _metric_number(metrics, "latency_seconds", "average_latency_seconds")
    cost_amount = _estimated_cost_amount(metrics)
    failure_count = _metric_number(metrics, "failure_count") or 0
    repaint_count = _metric_number(metrics, "repaint_count") or 0

    score = 0.0
    if approved_asset_ready:
        score += 1000
    if attempt.status == "completed":
        score += 200
    elif attempt.status == "completed_with_warnings":
        score += 160
    elif terminal:
        score += 20
    score -= failure_count * 25
    score -= repaint_count * 10
    if cost_amount is not None:
        score -= cost_amount
    if latency_seconds is not None:
        score -= latency_seconds * 0.1

    return {
        "attempt_id": attempt.id,
        "task_id": attempt.task_id,
        "strategy_id": attempt.strategy_id,
        "strategy_version": attempt.strategy_version,
        "model_id": attempt.model_id,
        "status": attempt.status,
        "terminal": terminal,
        "approved_asset_ready": approved_asset_ready,
        "approved_asset_ids": approved_asset_ids,
        "recommendable": recommendable,
        "metrics": metrics,
        "estimated_cost_amount": cost_amount,
        "latency_seconds": latency_seconds,
        "score": round(score, 3),
    }


def _ab_recommendation_payload(
    group: ImageProductionAbGroup,
    *,
    eligible: bool,
    code: str,
    attempt_scores: list[dict[str, Any]],
    recommended_attempt_id: str | None = None,
    recommended_asset_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "group_id": group.id,
        "eligible": eligible,
        "code": code,
        "recommended_attempt_id": recommended_attempt_id,
        "recommended_asset_ids": recommended_asset_ids or [],
        "attempt_scores": attempt_scores,
        "automatic_adoption_allowed": False,
    }


def ab_winner_recommendation_payload(db: Session, group_id: str, user_id: str | None = None) -> dict[str, Any]:
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

    attempts = _ab_attempt_rows(db, group.id)
    attempt_scores = [_ab_attempt_score(db, attempt) for attempt in attempts]
    if group.winner_attempt_id or group.status in AB_DECISION_STATUSES or group.decision_json:
        return _ab_recommendation_payload(group, eligible=False, code="DECISION_EXISTS", attempt_scores=attempt_scores)
    if not attempts:
        return _ab_recommendation_payload(group, eligible=False, code="NO_ATTEMPTS", attempt_scores=attempt_scores)
    if any(not score["terminal"] for score in attempt_scores):
        return _ab_recommendation_payload(
            group,
            eligible=False,
            code="ATTEMPTS_NOT_TERMINAL",
            attempt_scores=attempt_scores,
        )

    recommendable_scores = [score for score in attempt_scores if score["recommendable"]]
    if not recommendable_scores:
        return _ab_recommendation_payload(
            group,
            eligible=False,
            code="NO_APPROVED_ASSET",
            attempt_scores=attempt_scores,
        )

    selected = sorted(
        recommendable_scores,
        key=lambda score: (
            -score["score"],
            score["estimated_cost_amount"] if score["estimated_cost_amount"] is not None else float("inf"),
            score["latency_seconds"] if score["latency_seconds"] is not None else float("inf"),
            score["attempt_id"],
        ),
    )[0]
    return _ab_recommendation_payload(
        group,
        eligible=True,
        code="WINNER_RECOMMENDED",
        recommended_attempt_id=selected["attempt_id"],
        recommended_asset_ids=selected["approved_asset_ids"],
        attempt_scores=attempt_scores,
    )
