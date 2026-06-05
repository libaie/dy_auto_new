from app.db_models import (
    ImageCreationAsset,
    ImageCreationTask,
    ImageProductionAbAttempt,
    ImageProductionAbGroup,
    ImageProductionMetric,
    ImageProductionStrategy,
)
from app.services.image_production_recommendation_service import (
    ab_winner_recommendation_payload,
    strategy_recommendation_payload,
)


def _strategy(db, *, strategy_id="strategy-1", version=1):
    row = ImageProductionStrategy(
        id=strategy_id,
        slug=strategy_id,
        name="Strategy 1",
        destination_role="storyboard_first_frame",
        supported_modes_json=["text_to_image"],
        version=version,
    )
    db.add(row)
    db.flush()
    return row


def _metric(db, *, strategy_id="strategy-1", strategy_version=1, model_id="model-1", **overrides):
    values = {
        "attempt_count": 10,
        "success_count": 10,
        "failure_count": 0,
        "ai_pass_count": 10,
        "human_pass_count": 10,
        "repaint_count": 0,
        "average_latency_seconds": 10,
        "average_cost_amount": 1,
        "currency": "CNY",
    }
    values.update(overrides)
    row = ImageProductionMetric(
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        model_id=model_id,
        **values,
    )
    db.add(row)
    db.flush()
    return row


def _ab_group(db, *, user_id="test-user-id", status="completed", winner_attempt_id=None, decision_json=None):
    row = ImageProductionAbGroup(
        user_id=user_id,
        source_request_hash="ab-recommendation-hash",
        prompt_snapshot_json={"prompt": "pick the strongest frame"},
        status=status,
        winner_attempt_id=winner_attempt_id,
        decision_json=decision_json or {},
    )
    db.add(row)
    db.flush()
    return row


def _image_task(db, *, status="completed", strategy=None, group_id=None):
    row = ImageCreationTask(
        request_hash=f"task-{status}-{strategy.id if strategy else 'none'}",
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status=status,
        prompt="attempt frame",
        count=1,
        target_count=1,
        completed_count=1 if status in {"completed", "completed_with_warnings"} else 0,
        failed_count=1 if status == "failed" else 0,
        strategy_id=strategy.id if strategy else None,
        strategy_version=strategy.version if strategy else None,
        ab_test_group_id=group_id,
    )
    db.add(row)
    db.flush()
    return row


def _ab_attempt(db, group, strategy, *, status="completed", approved=False, metrics=None):
    task = _image_task(db, status=status, strategy=strategy, group_id=group.id)
    attempt = ImageProductionAbAttempt(
        group_id=group.id,
        task_id=task.id,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        status=status,
        metrics_snapshot_json=metrics or {},
    )
    db.add(attempt)
    db.flush()
    if approved:
        db.add(ImageCreationAsset(
            task_id=task.id,
            status="approved",
            url=f"https://img.example/{strategy.id}.png",
            slot_key=f"winner-{strategy.id}",
            version=1,
        ))
        db.flush()
    return attempt


def _recommendation_codes(payload):
    return [item["code"] for item in payload["recommendations"]]


def test_strategy_recommendation_is_cautious_for_low_sample(db):
    strategy = _strategy(db)
    _metric(db, attempt_count=2, success_count=2, ai_pass_count=2, human_pass_count=2)

    payload = strategy_recommendation_payload(db, strategy.id)

    assert payload["strategy_id"] == strategy.id
    assert payload["strategy_version"] == strategy.version
    assert payload["metrics"]["attempt_count"] == 2
    assert payload["status"] == "cautious"
    assert payload["confidence"] == "low"
    assert _recommendation_codes(payload) == ["LOW_SAMPLE"]
    assert payload["automatic_mutation_allowed"] is False


def test_strategy_recommendation_flags_high_failures_and_repaint(db):
    strategy = _strategy(db)
    _metric(
        db,
        attempt_count=10,
        success_count=6,
        failure_count=4,
        ai_pass_count=5,
        human_pass_count=5,
        repaint_count=4,
    )

    payload = strategy_recommendation_payload(db, strategy.id)

    assert payload["status"] == "cautious"
    assert payload["confidence"] == "medium"
    assert _recommendation_codes(payload) == ["HIGH_FAILURE_RATE", "HIGH_REPAINT_RATE"]
    assert payload["quality_score"] < 70
    assert payload["automatic_mutation_allowed"] is False


def test_strategy_recommendation_keeps_strong_strategy(db):
    strategy = _strategy(db)
    _metric(
        db,
        attempt_count=30,
        success_count=29,
        failure_count=1,
        ai_pass_count=28,
        human_pass_count=27,
        repaint_count=1,
    )

    payload = strategy_recommendation_payload(db, strategy.id)

    assert payload["status"] == "recommended"
    assert payload["confidence"] == "high"
    assert payload["quality_score"] >= 85
    assert _recommendation_codes(payload) == ["KEEP_STRATEGY"]
    assert payload["automatic_mutation_allowed"] is False


def test_ab_winner_recommendation_payload_selects_only_approved_completed_attempt(db):
    group = _ab_group(db)
    approved_strategy = _strategy(db, strategy_id="approved-strategy")
    rejected_strategy = _strategy(db, strategy_id="rejected-strategy")
    winner = _ab_attempt(
        db,
        group,
        approved_strategy,
        approved=True,
        metrics={"latency_seconds": 9, "estimated_cost": {"amount": 2.0}},
    )
    _ab_attempt(
        db,
        group,
        rejected_strategy,
        approved=False,
        metrics={"latency_seconds": 1, "estimated_cost": {"amount": 0.1}},
    )

    payload = ab_winner_recommendation_payload(db, group.id, user_id="test-user-id")

    assert payload["eligible"] is True
    assert payload["code"] == "WINNER_RECOMMENDED"
    assert payload["recommended_attempt_id"] == winner.id
    assert payload["automatic_adoption_allowed"] is False
    assert len(payload["attempt_scores"]) == 2
    selected_score = next(score for score in payload["attempt_scores"] if score["attempt_id"] == winner.id)
    assert selected_score["approved_asset_ready"] is True
    assert selected_score["recommendable"] is True


def test_ab_winner_recommendation_payload_returns_attempts_not_terminal(db):
    group = _ab_group(db, status="running")
    strategy_a = _strategy(db, strategy_id="running-strategy-a")
    strategy_b = _strategy(db, strategy_id="running-strategy-b")
    _ab_attempt(db, group, strategy_a, status="completed", approved=True)
    running = _ab_attempt(db, group, strategy_b, status="running", approved=False)

    payload = ab_winner_recommendation_payload(db, group.id, user_id="test-user-id")

    assert payload["eligible"] is False
    assert payload["code"] == "ATTEMPTS_NOT_TERMINAL"
    assert payload["recommended_attempt_id"] is None
    assert payload["automatic_adoption_allowed"] is False
    assert len(payload["attempt_scores"]) == 2
    running_score = next(score for score in payload["attempt_scores"] if score["attempt_id"] == running.id)
    assert running_score["status"] == "running"
    assert running_score["terminal"] is False


def test_ab_winner_recommendation_payload_returns_no_approved_asset(db):
    group = _ab_group(db)
    strategy_a = _strategy(db, strategy_id="unapproved-strategy-a")
    strategy_b = _strategy(db, strategy_id="unapproved-strategy-b")
    _ab_attempt(db, group, strategy_a, status="completed", approved=False)
    _ab_attempt(db, group, strategy_b, status="failed", approved=False)

    payload = ab_winner_recommendation_payload(db, group.id, user_id="test-user-id")

    assert payload["eligible"] is False
    assert payload["code"] == "NO_APPROVED_ASSET"
    assert payload["recommended_attempt_id"] is None
    assert payload["automatic_adoption_allowed"] is False
    assert len(payload["attempt_scores"]) == 2


def test_ab_winner_recommendation_payload_treats_decision_json_as_decision_exists(db):
    group = _ab_group(db, decision_json={"reason": "already reviewed"})
    strategy = _strategy(db, strategy_id="decision-json-strategy")
    _ab_attempt(db, group, strategy, status="completed", approved=True)

    payload = ab_winner_recommendation_payload(db, group.id, user_id="test-user-id")

    assert payload["eligible"] is False
    assert payload["code"] == "DECISION_EXISTS"
    assert payload["recommended_attempt_id"] is None
    assert payload["automatic_adoption_allowed"] is False
