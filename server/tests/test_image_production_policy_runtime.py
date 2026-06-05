from app.db_models import ImageCreationTask, ImageProductionPolicyVersion, ImageProductionStrategy
from app.services.image_production_policy_runtime import (
    estimate_image_cost,
    preview_image_capacity,
    preview_review_gate,
)


def _policy(db, policy_type, snapshot):
    row = ImageProductionPolicyVersion(
        policy_type=policy_type,
        name=f"{policy_type}-phase3",
        version=1,
        snapshot_json=snapshot,
        status="active",
    )
    db.add(row)
    db.commit()
    return row


def _strategy(db, *, cost_policy=None, capacity_policy=None, review_policy=None):
    row = ImageProductionStrategy(
        slug="phase3-strategy",
        name="Phase 3 Strategy",
        destination_role="image_to_video_input",
        supported_modes_json=["text_to_image"],
        common_parameters_json={},
        provider_options_json={},
        fallback_model_ids_json=[],
        cost_policy_version_id=cost_policy.id if cost_policy else None,
        capacity_policy_version_id=capacity_policy.id if capacity_policy else None,
        review_policy_version_id=review_policy.id if review_policy else None,
        status="active",
        version=1,
    )
    db.add(row)
    db.commit()
    return row


def test_estimate_image_cost_uses_policy_threshold(db):
    cost_policy = _policy(db, "cost", {
        "unit_cost": 1.25,
        "currency": "CNY",
        "confirmation_threshold": 2.0,
        "latency_seconds_per_image": 8,
    })
    strategy = _strategy(db, cost_policy=cost_policy)

    result = estimate_image_cost(db, {"count": 2}, strategy, {"provider": "mock"})

    assert result["amount"] == 2.5
    assert result["currency"] == "CNY"
    assert result["estimate_source"] == "policy"
    assert result["requires_confirmation"] is True
    assert result["confirmation_threshold"] == 2.0
    assert result["units"] == {"images": 2, "unit_cost": 1.25}
    assert result["policy_version_id"] == cost_policy.id
    assert result["time_estimate"] == {"estimated_seconds": 16, "estimate_source": "policy"}

    override_result = estimate_image_cost(db, {"count": 2}, strategy, {
        "config": {
            "cost_profile": {
                "unit_cost": 3.5,
                "currency": "USD",
            },
        },
    })

    assert override_result["amount"] == 7.0
    assert override_result["currency"] == "USD"
    assert override_result["units"] == {"images": 2, "unit_cost": 3.5}


def test_estimate_image_cost_includes_ab_group_cap(db):
    cost_policy = _policy(db, "cost", {
        "unit_cost": 2.0,
        "currency": "CNY",
        "confirmation_threshold": 1.0,
        "latency_seconds_per_image": 8,
        "ab_max_group_cost": 5.0,
    })
    strategy = _strategy(db, cost_policy=cost_policy)

    result = estimate_image_cost(db, {"count": 2}, strategy, {"provider": "mock"})

    assert result["amount"] == 4.0
    assert result["ab_max_group_cost"] == 5.0


def test_estimate_image_cost_omits_missing_ab_group_cap(db):
    result = estimate_image_cost(db, {"count": 2}, None, {"provider": "mock"})

    assert result["amount"] == 2.0
    assert "ab_max_group_cost" not in result


def test_estimate_image_cost_omits_blank_ab_group_cap(db):
    cost_policy = _policy(db, "cost", {
        "unit_cost": 2.0,
        "currency": "CNY",
        "confirmation_threshold": 1.0,
        "latency_seconds_per_image": 8,
        "ab_max_group_cost": "   ",
    })
    strategy = _strategy(db, cost_policy=cost_policy)

    result = estimate_image_cost(db, {"count": 2}, strategy, {"provider": "mock"})

    assert result["amount"] == 4.0
    assert "ab_max_group_cost" not in result


def test_estimate_image_cost_converts_numeric_ab_group_cap_string(db):
    cost_policy = _policy(db, "cost", {
        "unit_cost": 2.0,
        "currency": "CNY",
        "confirmation_threshold": 1.0,
        "latency_seconds_per_image": 8,
        "ab_max_group_cost": "5.0",
    })
    strategy = _strategy(db, cost_policy=cost_policy)

    result = estimate_image_cost(db, {"count": 2}, strategy, {"provider": "mock"})

    assert result["ab_max_group_cost"] == 5.0
    assert isinstance(result["ab_max_group_cost"], float)


def test_preview_image_capacity_counts_active_tasks(db):
    capacity_policy = _policy(db, "capacity", {
        "mode": "admission_control",
        "max_concurrent": 1,
        "average_task_seconds": 30,
        "queue_when_full": True,
    })
    strategy = _strategy(db, capacity_policy=capacity_policy)
    db.add(ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="running",
        prompt="busy",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id="model-1",
        capacity_lease_id="lease-running",
    ))
    db.commit()

    result = preview_image_capacity(db, strategy, "model-1")

    assert result["status"] == "queued"
    assert result["active_count"] == 1
    assert result["queue_depth"] == 1
    assert result["estimated_wait_seconds"] == 30
    assert result["admission_action"] == "queue"


def test_preview_image_capacity_counts_leased_queued_tasks_as_active(db):
    capacity_policy = _policy(db, "capacity", {
        "mode": "admission_control",
        "max_concurrent": 1,
        "average_task_seconds": 30,
        "queue_when_full": True,
    })
    strategy = _strategy(db, capacity_policy=capacity_policy)
    db.add(ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="queued",
        prompt="leased queued",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id="model-1",
        capacity_lease_id="lease-queued",
    ))
    db.commit()

    result = preview_image_capacity(db, strategy, "model-1")

    assert result["status"] == "queued"
    assert result["active_count"] == 1
    assert result["queued_count"] == 0
    assert result["queue_depth"] == 1
    assert result["estimated_wait_seconds"] == 30
    assert result["admission_action"] == "queue"


def test_preview_image_capacity_increments_existing_waiting_queue_depth(db):
    capacity_policy = _policy(db, "capacity", {
        "mode": "admission_control",
        "max_concurrent": 1,
        "average_task_seconds": 30,
        "queue_when_full": True,
    })
    strategy = _strategy(db, capacity_policy=capacity_policy)
    db.add_all([
        ImageCreationTask(
            mode="text_to_image",
            output_mode="single",
            capability_key="text_to_image",
            status="queued",
            prompt="leased queued",
            count=1,
            target_count=1,
            strategy_id=strategy.id,
            strategy_version=strategy.version,
            model_id="model-1",
            capacity_lease_id="lease-queued",
        ),
        ImageCreationTask(
            mode="text_to_image",
            output_mode="single",
            capability_key="text_to_image",
            status="queued",
            prompt="waiting",
            count=1,
            target_count=1,
            strategy_id=strategy.id,
            strategy_version=strategy.version,
            model_id="model-1",
            queue_job_id="queue-job-1",
        ),
    ])
    db.commit()

    result = preview_image_capacity(db, strategy, "model-1")

    assert result["active_count"] == 1
    assert result["queued_count"] == 1
    assert result["queue_depth"] == 2
    assert result["estimated_wait_seconds"] == 60
    assert result["admission_action"] == "queue"


def test_preview_image_capacity_blocks_when_full_and_queue_disabled(db):
    capacity_policy = _policy(db, "capacity", {
        "mode": "admission_control",
        "max_concurrent": 1,
        "average_task_seconds": 30,
        "queue_when_full": False,
    })
    strategy = _strategy(db, capacity_policy=capacity_policy)
    db.add(ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="queued",
        prompt="leased queued",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id="model-1",
        capacity_lease_id="lease-queued",
    ))
    db.commit()

    result = preview_image_capacity(db, strategy, "model-1")

    assert result["status"] == "blocked"
    assert result["active_count"] == 1
    assert result["queued_count"] == 0
    assert result["queue_depth"] == 0
    assert result["admission_action"] == "block"


def test_preview_only_capacity_policy_never_blocks_or_queues(db):
    capacity_policy = _policy(db, "capacity", {
        "mode": "preview_only",
        "max_concurrent": 1,
        "average_task_seconds": 30,
        "queue_when_full": False,
    })
    strategy = _strategy(db, capacity_policy=capacity_policy)
    db.add(ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="queued",
        prompt="leased queued",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id="model-1",
        capacity_lease_id="lease-queued",
    ))
    db.commit()

    result = preview_image_capacity(db, strategy, "model-1")

    assert result["mode"] == "preview_only"
    assert result["status"] == "available"
    assert result["active_count"] == 1
    assert result["queued_count"] == 0
    assert result["queue_depth"] == 0
    assert result["estimated_wait_seconds"] == 0
    assert result["admission_action"] == "submit_now"


def test_preview_image_capacity_ignores_admission_pending_tasks(db):
    capacity_policy = _policy(db, "capacity", {
        "mode": "admission_control",
        "max_concurrent": 1,
        "average_task_seconds": 30,
        "queue_when_full": True,
    })
    strategy = _strategy(db, capacity_policy=capacity_policy)
    db.add(ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="admission_pending",
        prompt="pending",
        count=1,
        target_count=1,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id="model-1",
        queue_job_id="queue-job-pending",
        capacity_lease_id="lease-pending",
    ))
    db.commit()

    result = preview_image_capacity(db, strategy, "model-1")

    assert result["status"] == "available"
    assert result["active_count"] == 0
    assert result["queued_count"] == 0
    assert result["queue_depth"] == 0
    assert result["admission_action"] == "submit_now"


def test_preview_review_gate_requires_manual_for_video_input(db):
    review_policy = _policy(db, "review", {
        "manual_required_for": ["image_to_video_input"],
        "ai_required_for": ["character_anchor_image"],
    })
    strategy = _strategy(db, review_policy=review_policy)

    result = preview_review_gate(db, strategy, "image_to_video_input")

    assert result["required"] is True
    assert result["manual_required"] is True
    assert result["ai_required"] is False
    assert result["status"] == "manual_review_pending"
