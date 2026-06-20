from datetime import timedelta

from app.config import bj_now
from app.db.models import (
    ImageCreationAsset,
    ImageCreationReviewRecord,
    ImageCreationTask,
    ImageProductionCostEvent,
    ImageProductionMetric,
)
from app.domains.image_generation.image_production_metrics_service import (
    aggregate_strategy_metrics_payload,
    refresh_all_image_strategy_metrics,
    refresh_image_strategy_metrics,
    strategy_metrics_payload,
)


def _task(
    db,
    *,
    task_id,
    status="completed",
    strategy_id="strategy-1",
    strategy_version=1,
    model_id="model-1",
    created_at=None,
    completed_at=None,
):
    created_at = created_at or bj_now() - timedelta(seconds=10)
    completed_at = completed_at if completed_at is not None else bj_now()
    task = ImageCreationTask(
        id=task_id,
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status=status,
        prompt=f"prompt {task_id}",
        count=1,
        target_count=1,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        model_id=model_id,
        created_at=created_at,
        completed_at=completed_at,
    )
    db.add(task)
    db.flush()
    return task


def test_refresh_image_strategy_metrics_counts_task_asset_review_and_cost(db):
    task = _task(db, task_id="metric-task-1", strategy_version=2)
    asset = ImageCreationAsset(
        task_id=task.id,
        url="https://img.example/a.png",
        status="approved",
        audit_status="approved",
    )
    db.add(asset)
    db.flush()
    db.add(
        ImageCreationReviewRecord(
            asset_id=asset.id,
            task_id=task.id,
            review_type="manual",
            status="approved",
            action="approve",
            asset_version=1,
            is_latest_asset_review=True,
        )
    )
    db.add(
        ImageProductionCostEvent(
            event_key="metric-task-1:actual:current",
            task_id=task.id,
            event_type="actual",
            actual_cost=1.2,
            estimated_cost=1.0,
            currency="CNY",
        )
    )
    db.commit()

    metric = refresh_image_strategy_metrics(db, "strategy-1", 2, "model-1")
    payload = strategy_metrics_payload(metric)

    assert payload["attempt_count"] == 1
    assert payload["success_rate"] == 1.0
    assert payload["ai_pass_rate"] == 1.0
    assert payload["human_pass_rate"] == 1.0
    assert payload["average_cost_amount"] == 1.2
    assert payload["low_sample"] is True


def test_refresh_image_strategy_metrics_counts_latest_actual_cost_once_per_task(db):
    task = _task(db, task_id="metric-task-2")
    db.add(
        ImageProductionCostEvent(
            event_key="metric-task-2:actual:first",
            task_id=task.id,
            event_type="actual",
            actual_cost=2.0,
            estimated_cost=1.0,
            currency="CNY",
            created_at=bj_now() - timedelta(seconds=2),
        )
    )
    db.add(
        ImageProductionCostEvent(
            event_key="metric-task-2:actual:second",
            task_id=task.id,
            event_type="actual",
            actual_cost=3.0,
            estimated_cost=1.0,
            currency="CNY",
            created_at=bj_now(),
        )
    )
    db.commit()

    metric = refresh_image_strategy_metrics(db, "strategy-1", 1, "model-1")

    assert strategy_metrics_payload(metric)["average_cost_amount"] == 3.0


def test_refresh_image_strategy_metrics_counts_failure_and_latency(db):
    completed_at = bj_now()
    _task(
        db,
        task_id="metric-task-failed",
        status="failed",
        created_at=completed_at - timedelta(seconds=12),
        completed_at=completed_at,
    )
    db.commit()

    metric = refresh_image_strategy_metrics(db, "strategy-1", 1, "model-1")
    payload = strategy_metrics_payload(metric)

    assert payload["attempt_count"] == 1
    assert payload["failure_count"] == 1
    assert payload["success_rate"] == 0.0
    assert payload["average_latency_seconds"] == 12.0


def test_refresh_image_strategy_metrics_counts_completed_with_warnings_as_success(db):
    _task(db, task_id="metric-task-warning", status="completed_with_warnings")
    db.commit()

    metric = refresh_image_strategy_metrics(db, "strategy-1", 1, "model-1")
    payload = strategy_metrics_payload(metric)

    assert payload["attempt_count"] == 1
    assert payload["success_count"] == 1
    assert payload["failure_count"] == 0
    assert payload["success_rate"] == 1.0


def test_refresh_image_strategy_metrics_does_not_count_ai_review_as_human_pass(db):
    task = _task(db, task_id="metric-task-ai-review")
    asset = ImageCreationAsset(
        task_id=task.id,
        url="https://img.example/ai-review.png",
        status="approved",
        audit_status="approved",
    )
    db.add(asset)
    db.flush()
    db.add(
        ImageCreationReviewRecord(
            asset_id=asset.id,
            task_id=task.id,
            review_type="ai",
            reviewer_type="ai",
            status="approved",
            action="approve",
            asset_version=1,
            is_latest_asset_review=True,
        )
    )
    db.commit()

    metric = refresh_image_strategy_metrics(db, "strategy-1", 1, "model-1")
    payload = strategy_metrics_payload(metric)

    assert payload["ai_pass_rate"] == 1.0
    assert payload["human_pass_rate"] == 0.0


def test_refresh_image_strategy_metrics_counts_multiple_assets_and_reviews_once_per_task(db):
    task = _task(db, task_id="metric-task-multiple-assets")
    asset_1 = ImageCreationAsset(
        task_id=task.id,
        url="https://img.example/asset-1.png",
        status="regenerating",
        audit_status="approved",
        slot_key="asset-1",
    )
    asset_2 = ImageCreationAsset(
        task_id=task.id,
        url="https://img.example/asset-2.png",
        status="approved",
        audit_status="approved",
        slot_key="asset-2",
        source_asset_id=asset_1.id,
    )
    db.add_all([asset_1, asset_2])
    db.flush()
    db.add_all(
        [
            ImageCreationReviewRecord(
                asset_id=asset_1.id,
                task_id=task.id,
                review_type="manual",
                reviewer_type="human",
                status="approved",
                action="approve",
                asset_version=1,
                is_latest_asset_review=True,
            ),
            ImageCreationReviewRecord(
                asset_id=asset_2.id,
                task_id=task.id,
                review_type="human",
                status="approved",
                action="approve",
                asset_version=1,
                is_latest_asset_review=True,
            ),
        ]
    )
    db.commit()

    metric = refresh_image_strategy_metrics(db, "strategy-1", 1, "model-1")
    payload = strategy_metrics_payload(metric)

    assert metric.ai_pass_count == 1
    assert metric.human_pass_count == 1
    assert metric.repaint_count == 1
    assert payload["ai_pass_rate"] == 1.0
    assert payload["human_pass_rate"] == 1.0


def test_refresh_image_strategy_metrics_uses_deterministic_actual_cost_tie_break(db):
    task = _task(db, task_id="metric-task-cost-tie")
    created_at = bj_now()
    db.add_all(
        [
            ImageProductionCostEvent(
                id="cost-event-a",
                event_key="metric-task-cost-tie:actual:a",
                task_id=task.id,
                event_type="actual",
                actual_cost=2.0,
                estimated_cost=1.0,
                currency="CNY",
                created_at=created_at,
            ),
            ImageProductionCostEvent(
                id="cost-event-b",
                event_key="metric-task-cost-tie:actual:b",
                task_id=task.id,
                event_type="actual",
                actual_cost=4.0,
                estimated_cost=1.0,
                currency="USD",
                created_at=created_at,
            ),
        ]
    )
    db.commit()

    metric = refresh_image_strategy_metrics(db, "strategy-1", 1, "model-1")
    payload = strategy_metrics_payload(metric)

    assert payload["average_cost_amount"] == 4.0
    assert payload["currency"] == "USD"


def test_refresh_image_strategy_metrics_does_not_commit_unrelated_pending_changes(db, monkeypatch):
    _task(db, task_id="metric-task-no-commit")
    commit_called = False

    def fail_commit():
        nonlocal commit_called
        commit_called = True
        raise AssertionError("refresh_image_strategy_metrics must not commit")

    monkeypatch.setattr(db, "commit", fail_commit)

    metric = refresh_image_strategy_metrics(db, "strategy-1", 1, "model-1")

    assert metric.attempt_count == 1
    assert commit_called is False


def test_refresh_image_strategy_metrics_reuses_metric_for_null_model_id(db):
    _task(db, task_id="metric-task-null-model", model_id=None)
    db.commit()

    first = refresh_image_strategy_metrics(db, "strategy-1", 1, None)
    second = refresh_image_strategy_metrics(db, "strategy-1", 1, None)
    metrics = (
        db.query(ImageProductionMetric)
        .filter(ImageProductionMetric.strategy_id == "strategy-1")
        .filter(ImageProductionMetric.strategy_version == 1)
        .filter(ImageProductionMetric.model_id.is_(None))
        .all()
    )

    assert first.id == second.id
    assert len(metrics) == 1
    assert strategy_metrics_payload(second)["attempt_count"] == 1


def test_aggregate_strategy_metrics_payload_weights_latency_cost_and_currency():
    metrics = [
        ImageProductionMetric(
            strategy_id="strategy-aggregate",
            strategy_version=1,
            model_id="model-a",
            attempt_count=2,
            success_count=1,
            failure_count=1,
            ai_pass_count=1,
            human_pass_count=0,
            repaint_count=1,
            average_latency_seconds=10,
            average_cost_amount=2,
            currency="CNY",
            updated_at=bj_now() - timedelta(seconds=1),
        ),
        ImageProductionMetric(
            strategy_id="strategy-aggregate",
            strategy_version=1,
            model_id="model-b",
            attempt_count=3,
            success_count=3,
            failure_count=0,
            ai_pass_count=2,
            human_pass_count=1,
            repaint_count=0,
            average_latency_seconds=20,
            average_cost_amount=4,
            currency="USD",
            updated_at=bj_now(),
        ),
    ]

    payload = aggregate_strategy_metrics_payload(metrics)

    assert payload["attempt_count"] == 5
    assert payload["success_count"] == 4
    assert payload["failure_count"] == 1
    assert payload["success_rate"] == 0.8
    assert payload["ai_pass_rate"] == 0.6
    assert payload["human_pass_rate"] == 0.2
    assert payload["repaint_count"] == 1
    assert payload["average_latency_seconds"] == 16
    assert payload["average_cost_amount"] == 3.2
    assert payload["currency"] == "MIXED"
    assert payload["low_sample"] is False
    assert payload["updated_at"] == metrics[1].updated_at.isoformat()


def test_aggregate_strategy_metrics_payload_defaults_currency_and_low_sample():
    payload = aggregate_strategy_metrics_payload([
        ImageProductionMetric(
            strategy_id="strategy-aggregate",
            strategy_version=1,
            model_id="model-a",
            attempt_count=4,
            success_count=2,
            currency=None,
        )
    ])

    assert payload["currency"] == "CNY"
    assert payload["low_sample"] is True


def test_refresh_all_image_strategy_metrics_refreshes_observed_keys(db):
    _task(db, task_id="batch-task-a", strategy_id="strategy-a", strategy_version=1, model_id="model-a")
    _task(db, task_id="batch-task-b", strategy_id="strategy-a", strategy_version=1, model_id="model-a")
    _task(db, task_id="batch-task-c", strategy_id="strategy-a", strategy_version=1, model_id=None)
    _task(db, task_id="batch-task-d", strategy_id="strategy-b", strategy_version=2, model_id="model-b")
    _task(db, task_id="batch-task-missing-strategy", strategy_id=None, strategy_version=1, model_id="model-c")
    _task(db, task_id="batch-task-missing-version", strategy_id="strategy-c", strategy_version=None, model_id="model-c")
    db.commit()

    result = refresh_all_image_strategy_metrics(db)

    assert result == {
        "refreshed_count": 3,
        "keys": [
            {"strategy_id": "strategy-a", "strategy_version": 1, "model_id": None},
            {"strategy_id": "strategy-a", "strategy_version": 1, "model_id": "model-a"},
            {"strategy_id": "strategy-b", "strategy_version": 2, "model_id": "model-b"},
        ],
    }
    assert db.query(ImageProductionMetric).count() == 3


def test_refresh_all_image_strategy_metrics_filters_strategy_id(db):
    _task(db, task_id="batch-filter-a", strategy_id="strategy-a", strategy_version=1, model_id="model-a")
    _task(db, task_id="batch-filter-b", strategy_id="strategy-b", strategy_version=1, model_id="model-b")
    db.commit()

    result = refresh_all_image_strategy_metrics(db, strategy_id="strategy-a")

    assert result == {
        "refreshed_count": 1,
        "keys": [
            {"strategy_id": "strategy-a", "strategy_version": 1, "model_id": "model-a"},
        ],
    }
    metrics = db.query(ImageProductionMetric).all()
    assert len(metrics) == 1
    assert metrics[0].strategy_id == "strategy-a"
