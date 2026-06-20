from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.domains.image_generation import image_creation_service
from app.db.models import (
    AIModel,
    ImageCreationAsset,
    ImageCreationTask,
    ImageProductionAbAttempt,
    ImageProductionAbGroup,
    ImageProductionPolicyVersion,
    ImageProductionStrategy,
    ImageSelectionPreview,
    ProductionAuditEvent,
)
from app.domains.image_generation import image_ab_test_service as service
from app.domains.system_configuration.crypto import encrypt


def _model(db):
    row = AIModel(
        name="AB Image Model",
        provider="seedance",
        model_type="image",
        model_name="seedream-ab",
        enabled=True,
        base_url="https://example.invalid",
        api_key=encrypt("secret-key"),
        config_json={
            "scene_key": "image_generation",
            "scene_keys": ["image_generation"],
            "capabilities": {"text_to_image": True},
            "cost_profile": {"unit_cost": 1.5, "currency": "CNY"},
        },
    )
    db.add(row)
    db.commit()
    return row


def _cost_policy(db, cap=None, unit_cost=1.5):
    row = ImageProductionPolicyVersion(
        policy_type="cost",
        name=f"ab-cost-{cap}-{unit_cost}",
        version=1,
        snapshot_json={
            "unit_cost": unit_cost,
            "currency": "CNY",
            "confirmation_threshold": 1.0,
            "ab_max_group_cost": cap,
        },
        status="active",
    )
    db.add(row)
    db.commit()
    return row


def _strategy(db, model, slug, cost_policy=None, status="active"):
    row = ImageProductionStrategy(
        slug=slug,
        name=slug,
        destination_role="storyboard_first_frame",
        supported_modes_json=["text_to_image"],
        default_model_id=model.id,
        fallback_model_ids_json=[],
        common_parameters_json={},
        provider_options_json={},
        cost_policy_version_id=cost_policy.id if cost_policy else None,
        status=status,
        version=1,
    )
    db.add(row)
    db.commit()
    return row


def _payload(strategies, **overrides):
    payload = {
        "mode": "text_to_image",
        "prompt": "A clean storyboard frame",
        "negative_prompt": "",
        "destination_role": "storyboard_first_frame",
        "strategy_ids": [strategy.id for strategy in strategies],
        "count": 1,
        "provider_options": {},
        "cost_confirmation": True,
        "idempotency_key": "ab-group-1",
    }
    payload.update(overrides)
    return payload


def _task(db, *, status="completed", strategy=None, idempotency_key=None, ab_group_id=None, user_id=None):
    row = ImageCreationTask(
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_hash=f"request-{idempotency_key or status}",
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status=status,
        prompt="attempt frame",
        count=1,
        target_count=1,
        completed_count=1 if status == "completed" else 0,
        failed_count=1 if status == "failed" else 0,
        model_id=strategy.default_model_id if strategy else "model-1",
        strategy_id=strategy.id if strategy else None,
        strategy_version=strategy.version if strategy else None,
        ab_test_group_id=ab_group_id,
    )
    db.add(row)
    db.commit()
    return row


def _approved_asset(db, task):
    row = ImageCreationAsset(
        task_id=task.id,
        url="https://img.example/approved.png",
        prompt=task.prompt,
        status="approved",
        version=1,
        slot_key="default",
    )
    db.add(row)
    db.commit()
    return row


def _image_asset(db, task, *, user_id="test-user-id"):
    row = ImageCreationAsset(
        task_id=task.id,
        user_id=user_id,
        url="https://img.example/source.png",
        prompt=task.prompt,
        status="approved",
        version=1,
        slot_key="source",
    )
    db.add(row)
    db.commit()
    return row


def _group_with_attempts(db, strategies, *, task_status="completed", approved=False):
    group = ImageProductionAbGroup(
        user_id="test-user-id",
        idempotency_key="decision-group",
        source_request_hash="hash-decision",
        prompt_snapshot_json=_payload(strategies),
        cost_confirmation_json={"confirmed": True},
        status="completed",
    )
    db.add(group)
    db.flush()
    attempts = []
    for index, strategy in enumerate(strategies):
        task = _task(
            db,
            status=task_status,
            strategy=strategy,
            idempotency_key=f"decision-{index}",
            ab_group_id=group.id,
        )
        if approved and index == 0:
            _approved_asset(db, task)
        attempt = ImageProductionAbAttempt(
            group_id=group.id,
            task_id=task.id,
            strategy_id=strategy.id,
            strategy_version=strategy.version,
            model_id=strategy.default_model_id,
            status=task_status,
            metrics_snapshot_json={"latency_seconds": 8 + index, "cost_amount": 1.5},
        )
        db.add(attempt)
        attempts.append(attempt)
    db.commit()
    return group, attempts


def _assert_image_error(exc_info, status_code, error_code):
    assert isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == status_code
    assert exc_info.value.detail["error_code"] == error_code


def _preview_event(db):
    return db.query(ProductionAuditEvent).filter_by(event_type="image_ab.preview").one()


def _set_preview_event_payload(db, event, payload):
    event.payload_json = payload
    db.commit()


def test_preview_ab_group_requires_multiple_strategies(db):
    model = _model(db)
    strategy = _strategy(db, model, "only-one")

    with pytest.raises(HTTPException) as exc:
        service.preview_ab_group(db, _payload([strategy]), user_id="test-user-id")

    _assert_image_error(exc, 422, "IMAGE_AB_TEST_STRATEGY_COUNT_INVALID")


def test_preview_ab_group_returns_total_cost_and_request_hash(db):
    model = _model(db)
    cost_policy = _cost_policy(db)
    strategies = [
        _strategy(db, model, "variant-a", cost_policy),
        _strategy(db, model, "variant-b", cost_policy),
    ]

    preview = service.preview_ab_group(db, _payload(strategies), user_id="test-user-id")

    assert preview["ok"] is True
    assert preview["strategy_count"] == 2
    assert preview["request_hash"]
    assert preview["total_cost_estimate"]["amount"] == 3.0
    assert preview["total_cost_estimate"]["currency"] == "CNY"
    assert preview["previews"][0]["strategy_id"] == strategies[0].id


def test_preview_ab_group_rejects_hashless_selection_preview_without_audit(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "hashless-a"), _strategy(db, model, "hashless-b")]

    def fake_create_selection_preview(db_arg, preview_payload, user_id=None):
        return {
            "ok": True,
            "request_hash": None,
            "cost_estimate": {"amount": 1.0, "currency": "CNY", "requires_confirmation": False},
        }

    monkeypatch.setattr(service, "create_selection_preview", fake_create_selection_preview)

    with pytest.raises(HTTPException) as exc:
        service.preview_ab_group(db, _payload(strategies), user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_PREVIEW_DRIFT")
    assert db.query(ProductionAuditEvent).filter_by(event_type="image_ab.preview").count() == 0


def test_preview_ab_group_returns_strictest_group_cost_cap(db):
    model = _model(db)
    capped = _cost_policy(db, cap=2.0)
    stricter = _cost_policy(db, cap=1.75)
    strategies = [
        _strategy(db, model, "capped", capped),
        _strategy(db, model, "stricter", stricter),
    ]

    preview = service.preview_ab_group(db, _payload(strategies), user_id="test-user-id")

    assert preview["total_cost_estimate"]["ab_max_group_cost"] == 1.75
    assert preview["total_cost_estimate"]["cost_limit_exceeded"] is True


def test_preview_ab_group_request_hash_includes_per_strategy_preview_hashes(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "hash-a"), _strategy(db, model, "hash-b")]
    preview_hash_sets = iter([
        ["strategy-a-v1", "strategy-b-v1"],
        ["strategy-a-v2", "strategy-b-v1"],
    ])
    current_hashes = []

    def fake_create_selection_preview(db_arg, preview_payload, user_id=None):
        return {
            "ok": True,
            "request_hash": current_hashes.pop(0),
            "cost_estimate": {"amount": 1.0, "currency": "CNY", "requires_confirmation": False},
            "selection_preview_request_hash": None,
        }

    monkeypatch.setattr(service, "create_selection_preview", fake_create_selection_preview)
    current_hashes.extend(next(preview_hash_sets))
    first = service.preview_ab_group(db, _payload(strategies), user_id="test-user-id")
    current_hashes.extend(next(preview_hash_sets))
    second = service.preview_ab_group(db, _payload(strategies), user_id="test-user-id")

    assert first["request_hash"] != second["request_hash"]


@pytest.mark.asyncio
async def test_create_ab_group_idempotent_retry_has_no_preview_side_effects(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]

    async def fake_create_image_task(db_arg, task_payload):
        return _task(
            db,
            status="queued",
            strategy=strategies[0],
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="no-side-effects")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    before_create_preview_events = db.query(ProductionAuditEvent).filter_by(event_type="image_ab.preview").count()

    first = await service.create_ab_group(db, payload, user_id="test-user-id")
    after_create_preview_events = db.query(ProductionAuditEvent).filter_by(event_type="image_ab.preview").count()

    def fail_preview(db_arg, preview_payload, user_id=None):
        raise AssertionError("idempotent retry must not create fresh selection previews")

    monkeypatch.setattr(service, "create_selection_preview", fail_preview)
    second = await service.create_ab_group(db, payload, user_id="test-user-id")

    assert second.id == first.id
    assert after_create_preview_events == before_create_preview_events
    assert db.query(ProductionAuditEvent).filter_by(event_type="image_ab.preview").count() == after_create_preview_events
    assert db.query(ProductionAuditEvent).filter_by(event_type="image_ab.create").count() == 1


@pytest.mark.asyncio
async def test_create_ab_group_uses_matching_user_preview_when_same_hash_exists_for_multiple_users(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "same-hash-user-a"), _strategy(db, model, "same-hash-user-b")]

    async def fake_create_image_task(db_arg, task_payload):
        strategy = strategies[0] if task_payload["strategy_id"] == strategies[0].id else strategies[1]
        return _task(
            db,
            status="queued",
            strategy=strategy,
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="same-hash-user-a-create")
    user_a_preview = service.preview_ab_group(db, payload, user_id="user-a")
    user_b_preview = service.preview_ab_group(db, payload, user_id="user-b")
    assert user_b_preview["request_hash"] == user_a_preview["request_hash"]

    group = await service.create_ab_group(
        db,
        {**payload, "preview_request_hash": user_a_preview["request_hash"]},
        user_id="user-a",
    )

    assert group.user_id == "user-a"
    assert group.status == "running"
    assert db.query(ImageProductionAbGroup).filter_by(id=group.id).count() == 1


@pytest.mark.asyncio
async def test_create_ab_group_missing_preview_hash_rejects_without_side_effects(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "missing-preview-a"), _strategy(db, model, "missing-preview-b")]

    def fail_preview(db_arg, preview_payload, user_id=None):
        raise AssertionError("create must not create fresh previews for missing preview hash")

    monkeypatch.setattr(service, "create_selection_preview", fail_preview)

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, _payload(strategies), user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_PREVIEW_DRIFT")
    assert db.query(ProductionAuditEvent).count() == 0
    assert db.query(ImageProductionAbGroup).count() == 0
    assert db.query(ImageProductionAbAttempt).count() == 0
    assert db.query(ImageCreationTask).count() == 0


@pytest.mark.asyncio
async def test_create_ab_group_rejects_preview_drift(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    payload = _payload(strategies, prompt="original prompt")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, {**payload, "prompt": "changed prompt"}, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_PREVIEW_DRIFT")


@pytest.mark.asyncio
async def test_create_ab_group_rejects_preview_drift_when_source_url_changes(db):
    model = _model(db)
    strategies = [_strategy(db, model, "source-a"), _strategy(db, model, "source-b")]
    payload = _payload(strategies, source_url="https://img.example/source-a.png")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(
            db,
            {**payload, "source_url": "https://img.example/source-b.png"},
            user_id="test-user-id",
        )

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_PREVIEW_DRIFT")


@pytest.mark.asyncio
async def test_create_ab_group_rejects_preview_drift_when_reference_image_changes(db):
    model = _model(db)
    strategies = [_strategy(db, model, "reference-a"), _strategy(db, model, "reference-b")]
    payload = _payload(strategies, reference_images=[{"url": "https://img.example/ref-a.png"}])
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(
            db,
            {**payload, "reference_images": [{"url": "https://img.example/ref-b.png"}]},
            user_id="test-user-id",
        )

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_PREVIEW_DRIFT")


@pytest.mark.asyncio
async def test_create_ab_group_creates_attempt_tasks_with_derived_idempotency(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    calls = []

    async def fake_create_image_task(db_arg, task_payload):
        calls.append(task_payload)
        return _task(
            db,
            status="queued",
            strategy=strategies[len(calls) - 1],
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="ab-fixed-key")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    group = await service.create_ab_group(db, payload, user_id="test-user-id")

    attempts = (
        db.query(ImageProductionAbAttempt)
        .filter_by(group_id=group.id)
        .order_by(ImageProductionAbAttempt.created_at.asc())
        .all()
    )
    assert group.status == "running"
    assert len(attempts) == 2
    assert calls[0]["ab_test_group_id"] == group.id
    assert calls[0]["idempotency_key"] == f"ab-fixed-key:attempt:0:{strategies[0].id}:{strategies[0].version}"
    assert calls[0]["selection_preview_id"]
    assert calls[0]["selection_preview_request_hash"]
    assert calls[1]["idempotency_key"] == f"ab-fixed-key:attempt:1:{strategies[1].id}:{strategies[1].version}"


@pytest.mark.asyncio
async def test_create_ab_group_reuses_group_idempotency_key_for_same_request(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]

    async def fake_create_image_task(db_arg, task_payload):
        return _task(
            db,
            status="queued",
            strategy=strategies[0],
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="stable-ab-key")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    first = await service.create_ab_group(db, payload, user_id="test-user-id")
    second = await service.create_ab_group(db, payload, user_id="test-user-id")

    assert second.id == first.id
    assert db.query(ImageProductionAbGroup).filter_by(idempotency_key="stable-ab-key").count() == 1


@pytest.mark.asyncio
async def test_create_ab_group_idempotent_retry_allows_duplicate_strategy_ids_after_normalization(db, monkeypatch):
    model = _model(db)
    strategy_a = _strategy(db, model, "duplicate-a")
    strategy_b = _strategy(db, model, "duplicate-b")
    strategies = [strategy_a, strategy_b, strategy_a]
    calls = []

    async def fake_create_image_task(db_arg, task_payload):
        calls.append(task_payload)
        strategy = strategy_a if task_payload["strategy_id"] == strategy_a.id else strategy_b
        return _task(
            db,
            status="queued",
            strategy=strategy,
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="duplicate-strategy-key")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    first = await service.create_ab_group(db, payload, user_id="test-user-id")
    second = await service.create_ab_group(db, payload, user_id="test-user-id")

    attempts = db.query(ImageProductionAbAttempt).filter_by(group_id=first.id).all()
    assert second.id == first.id
    assert len(attempts) == 2
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_create_ab_group_idempotent_retry_returns_existing_after_preview_expires(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "expired-retry-a"), _strategy(db, model, "expired-retry-b")]

    async def fake_create_image_task(db_arg, task_payload):
        return _task(
            db,
            status="queued",
            strategy=strategies[0],
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="expired-preview-retry")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    first = await service.create_ab_group(db, payload, user_id="test-user-id")
    event = _preview_event(db)
    event_payload = dict(event.payload_json)
    event_payload["previews"] = [
        {**preview, "expires_at": "2000-01-01T00:00:00"}
        for preview in event_payload["previews"]
    ]
    _set_preview_event_payload(db, event, event_payload)

    second = await service.create_ab_group(db, payload, user_id="test-user-id")

    assert second.id == first.id
    assert db.query(ImageProductionAbGroup).filter_by(idempotency_key="expired-preview-retry").count() == 1


@pytest.mark.parametrize(
    ("suffix", "changed_fields"),
    [
        ("prompt", {"prompt": "A changed storyboard frame"}),
        ("source", {"source_url": "https://img.example/source-b.png"}),
        ("reference", {"reference_images": [{"url": "https://img.example/ref-b.png"}]}),
        ("count", {"count": 2}),
    ],
)
@pytest.mark.asyncio
async def test_create_ab_group_idempotent_retry_rejects_payload_changes_with_old_preview_hash(
    db,
    monkeypatch,
    suffix,
    changed_fields,
):
    model = _model(db)
    strategies = [_strategy(db, model, f"old-hash-{suffix}-a"), _strategy(db, model, f"old-hash-{suffix}-b")]

    async def fake_create_image_task(db_arg, task_payload):
        return _task(
            db,
            status="queued",
            strategy=strategies[0],
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(
        strategies,
        idempotency_key=f"old-preview-conflict-{suffix}",
        source_url="https://img.example/source-a.png",
        reference_images=[{"url": "https://img.example/ref-a.png"}],
    )
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    first = await service.create_ab_group(db, payload, user_id="test-user-id")
    changed = {**payload, **changed_fields}

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, changed, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_IDEMPOTENCY_CONFLICT")
    assert db.query(ImageProductionAbGroup).filter_by(id=first.id).count() == 1
    assert db.query(ImageProductionAbGroup).filter_by(idempotency_key=payload["idempotency_key"]).count() == 1


@pytest.mark.asyncio
async def test_create_ab_group_idempotent_retry_leaves_fresh_incomplete_group_running(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "fresh-incomplete-a"), _strategy(db, model, "fresh-incomplete-b")]
    payload = _payload(strategies, idempotency_key="fresh-incomplete-existing-retry")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    group = ImageProductionAbGroup(
        user_id="test-user-id",
        idempotency_key=payload["idempotency_key"],
        source_request_hash=payload["preview_request_hash"],
        prompt_snapshot_json=dict(payload),
        cost_confirmation_json={"confirmed": True},
        status="running",
    )
    db.add(group)
    db.flush()
    for strategy in strategies:
        db.add(
            ImageProductionAbAttempt(
                group_id=group.id,
                strategy_id=strategy.id,
                strategy_version=strategy.version,
                model_id=strategy.default_model_id,
                status="creating",
                metrics_snapshot_json={"selection_preview_request_hash": f"preview-{strategy.id}"},
            )
        )
    db.commit()

    async def fail_create_image_task(db_arg, task_payload):
        raise AssertionError("idempotent retry must not launch new tasks for an existing group")

    monkeypatch.setattr(service, "create_image_task", fail_create_image_task)

    retried = await service.create_ab_group(db, payload, user_id="test-user-id")

    attempts = db.query(ImageProductionAbAttempt).filter_by(group_id=group.id).all()
    assert retried.id == group.id
    assert retried.status == "running"
    assert {attempt.status for attempt in attempts} == {"creating"}
    assert all(attempt.task_id is None for attempt in attempts)
    assert all((attempt.metrics_snapshot_json or {}).get("error_code") is None for attempt in attempts)


@pytest.mark.asyncio
async def test_create_ab_group_idempotent_retry_marks_stale_incomplete_group_failed(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "stale-incomplete-a"), _strategy(db, model, "stale-incomplete-b")]
    payload = _payload(strategies, idempotency_key="stale-incomplete-existing-retry")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    stale_at = service.bj_now() - timedelta(minutes=30)
    group = ImageProductionAbGroup(
        user_id="test-user-id",
        idempotency_key=payload["idempotency_key"],
        source_request_hash=payload["preview_request_hash"],
        prompt_snapshot_json=dict(payload),
        cost_confirmation_json={"confirmed": True},
        status="running",
        created_at=stale_at,
        updated_at=stale_at,
    )
    db.add(group)
    db.flush()
    for index, strategy in enumerate(strategies):
        attempt_stale_at = stale_at + timedelta(seconds=index)
        db.add(
            ImageProductionAbAttempt(
                group_id=group.id,
                strategy_id=strategy.id,
                strategy_version=strategy.version,
                model_id=strategy.default_model_id,
                status="creating",
                metrics_snapshot_json={"selection_preview_request_hash": f"preview-{strategy.id}"},
                created_at=attempt_stale_at,
                updated_at=attempt_stale_at,
            )
        )
    db.commit()

    async def fail_create_image_task(db_arg, task_payload):
        raise AssertionError("idempotent retry must not launch new tasks for an existing group")

    monkeypatch.setattr(service, "create_image_task", fail_create_image_task)

    retried = await service.create_ab_group(db, payload, user_id="test-user-id")

    attempts = db.query(ImageProductionAbAttempt).filter_by(group_id=group.id).all()
    assert retried.id == group.id
    assert retried.status == "failed"
    assert {attempt.status for attempt in attempts} == {"failed"}
    assert all(attempt.task_id is None for attempt in attempts)
    assert {attempt.metrics_snapshot_json["error_code"] for attempt in attempts} == {"IMAGE_AB_TEST_ATTEMPT_INCOMPLETE"}
    assert all("selection_preview_request_hash" in attempt.metrics_snapshot_json for attempt in attempts)


@pytest.mark.asyncio
async def test_create_ab_group_idempotent_retry_recovers_orphaned_attempt_tasks(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "recover-task-a"), _strategy(db, model, "recover-task-b")]
    payload = _payload(strategies, idempotency_key="recover-orphaned-task")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    group = ImageProductionAbGroup(
        user_id="test-user-id",
        idempotency_key=payload["idempotency_key"],
        source_request_hash=payload["preview_request_hash"],
        prompt_snapshot_json=dict(payload),
        cost_confirmation_json={"confirmed": True},
        status="running",
    )
    db.add(group)
    db.flush()
    tasks = []
    for index, strategy in enumerate(strategies):
        tasks.append(
            _task(
                db,
                status="queued",
                strategy=strategy,
                idempotency_key=f"{payload['idempotency_key']}:attempt:{index}:{strategy.id}:{strategy.version}",
                ab_group_id=group.id,
                user_id="test-user-id",
            )
        )
        db.add(
            ImageProductionAbAttempt(
                group_id=group.id,
                strategy_id=strategy.id,
                strategy_version=strategy.version,
                model_id=strategy.default_model_id,
                status="creating",
                metrics_snapshot_json={"selection_preview_request_hash": f"preview-{strategy.id}"},
            )
        )
    db.commit()

    async def fail_create_image_task(db_arg, task_payload):
        raise AssertionError("idempotent retry must recover existing task rows instead of launching new tasks")

    monkeypatch.setattr(service, "create_image_task", fail_create_image_task)

    retried = await service.create_ab_group(db, payload, user_id="test-user-id")

    attempts = (
        db.query(ImageProductionAbAttempt)
        .filter_by(group_id=group.id)
        .order_by(ImageProductionAbAttempt.created_at.asc(), ImageProductionAbAttempt.id.asc())
        .all()
    )
    assert retried.id == group.id
    assert retried.status == "running"
    assert [attempt.task_id for attempt in attempts] == [task.id for task in tasks]
    assert {attempt.status for attempt in attempts} == {"creating"}
    assert all((attempt.metrics_snapshot_json or {}).get("error_code") is None for attempt in attempts)


@pytest.mark.asyncio
async def test_create_ab_group_rejects_cross_user_idempotency_key_reuse(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "cross-user-key-a"), _strategy(db, model, "cross-user-key-b")]

    async def fake_create_image_task(db_arg, task_payload):
        return _task(
            db,
            status="queued",
            strategy=strategies[0],
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="shared-user-key")
    user_a_preview = service.preview_ab_group(db, payload, user_id="user-a")
    first = await service.create_ab_group(db, {**payload, "preview_request_hash": user_a_preview["request_hash"]}, user_id="user-a")
    user_b_preview = service.preview_ab_group(db, payload, user_id="user-b")

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, {**payload, "preview_request_hash": user_b_preview["request_hash"]}, user_id="user-b")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_IDEMPOTENCY_CONFLICT")
    assert first.id not in exc.value.detail.get("affected_ids", [])
    assert db.query(ImageProductionAbGroup).filter_by(idempotency_key="shared-user-key").count() == 1


@pytest.mark.asyncio
async def test_create_ab_group_rejects_idempotency_conflict(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]

    async def fake_create_image_task(db_arg, task_payload):
        return _task(
            db,
            status="queued",
            strategy=strategies[0],
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="conflict-ab-key")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    await service.create_ab_group(db, payload, user_id="test-user-id")
    changed = {**payload, "prompt": "different prompt"}
    changed["preview_request_hash"] = service.preview_ab_group(db, changed, user_id="test-user-id")["request_hash"]

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, changed, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_IDEMPOTENCY_CONFLICT")


@pytest.mark.asyncio
async def test_create_ab_group_rejects_idempotency_conflict_when_source_url_changes(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "conflict-source-a"), _strategy(db, model, "conflict-source-b")]

    async def fake_create_image_task(db_arg, task_payload):
        return _task(
            db,
            status="queued",
            strategy=strategies[0],
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="source-conflict", source_url="https://img.example/source-a.png")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    await service.create_ab_group(db, payload, user_id="test-user-id")
    changed = {**payload, "source_url": "https://img.example/source-b.png"}
    changed["preview_request_hash"] = service.preview_ab_group(db, changed, user_id="test-user-id")["request_hash"]

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, changed, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_IDEMPOTENCY_CONFLICT")


@pytest.mark.asyncio
async def test_create_ab_group_rejects_when_total_cost_exceeds_ab_group_cap(db):
    model = _model(db)
    policy = _cost_policy(db, cap=2.0)
    strategies = [_strategy(db, model, "variant-a", policy), _strategy(db, model, "variant-b", policy)]
    payload = _payload(strategies, idempotency_key="too-expensive")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    preview_event_count = db.query(ProductionAuditEvent).filter_by(event_type="image_ab.preview").count()

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, payload, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_COST_LIMIT_EXCEEDED")
    assert db.query(ProductionAuditEvent).filter_by(event_type="image_ab.preview").count() == preview_event_count
    assert db.query(ProductionAuditEvent).filter_by(event_type="image_ab.create").count() == 0
    assert db.query(ImageProductionAbGroup).count() == 0
    assert db.query(ImageProductionAbAttempt).count() == 0
    assert db.query(ImageCreationTask).count() == 0


@pytest.mark.asyncio
async def test_create_ab_group_revalidates_current_preview_before_side_effects(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "current-preview-a"), _strategy(db, model, "current-preview-b")]
    payload = _payload(strategies, idempotency_key="current-preview-drift")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    preview_calls = {"count": 0}

    def changed_selection_preview(db_arg, preview_payload, user_id=None):
        preview_calls["count"] += 1
        return {
            "ok": True,
            "request_hash": f"changed-current-preview-{preview_calls['count']}",
            "cost_estimate": {
                "amount": 1.0,
                "currency": "CNY",
                "requires_confirmation": False,
            },
            "selection_preview_id": f"current-preview-{preview_calls['count']}",
            "expires_at": (image_creation_service.bj_now() + timedelta(minutes=15)).isoformat(),
        }

    async def fake_create_image_task(db_arg, task_payload):
        return _task(
            db,
            status="queued",
            strategy=strategies[0],
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_selection_preview", changed_selection_preview)
    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, payload, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_PREVIEW_DRIFT")
    assert db.query(ImageProductionAbGroup).count() == 0
    assert db.query(ImageProductionAbAttempt).count() == 0
    assert db.query(ImageCreationTask).count() == 0


@pytest.mark.asyncio
async def test_create_ab_group_requires_ab_cost_confirmation_before_attempts(db, monkeypatch):
    model = _model(db)
    policy = _cost_policy(db, cap=10.0)
    strategies = [_strategy(db, model, "confirm-a", policy), _strategy(db, model, "confirm-b", policy)]

    async def fail_create_image_task(db_arg, task_payload):
        raise AssertionError("missing A/B cost confirmation must stop before attempts")

    monkeypatch.setattr(service, "create_image_task", fail_create_image_task)
    preview_payload = _payload(strategies, idempotency_key="missing-ab-confirm")
    preview_hash = service.preview_ab_group(db, preview_payload, user_id="test-user-id")["request_hash"]
    before_events = db.query(ProductionAuditEvent).count()
    create_payload = _payload(
        strategies,
        idempotency_key="missing-ab-confirm",
        cost_confirmation=False,
        preview_request_hash=preview_hash,
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, create_payload, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_COST_CONFIRMATION_REQUIRED")
    assert db.query(ImageProductionAbGroup).filter_by(idempotency_key="missing-ab-confirm").count() == 0
    assert db.query(ImageProductionAbAttempt).count() == 0
    assert db.query(ImageCreationTask).count() == 0
    assert db.query(ProductionAuditEvent).count() == before_events


@pytest.mark.asyncio
async def test_create_ab_group_cost_confirmed_actual_task_path_uses_ab_preview_hash(db, monkeypatch):
    model = _model(db)
    policy = _cost_policy(db, cap=10.0)
    strategies = [_strategy(db, model, "actual-a", policy), _strategy(db, model, "actual-b", policy)]
    calls = []

    async def fake_submit_image_create(**kwargs):
        calls.append(kwargs)
        return {"stage_task_id": f"stage-task-{len(calls)}"}

    monkeypatch.setattr(image_creation_service, "submit_image_create", fake_submit_image_create)
    payload = _payload(strategies, idempotency_key="actual-cost-confirmed")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    group = await service.create_ab_group(db, payload, user_id="test-user-id")

    attempts = db.query(ImageProductionAbAttempt).filter_by(group_id=group.id).all()
    tasks = db.query(ImageCreationTask).filter(ImageCreationTask.ab_test_group_id == group.id).all()
    assert group.status == "running"
    assert len(attempts) == 2
    assert all(attempt.task_id for attempt in attempts)
    assert {task.user_id for task in tasks} == {"test-user-id"}
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_create_image_task_rejects_fake_ab_hash_cost_confirmation_bypass(db, monkeypatch):
    model = _model(db)
    policy = _cost_policy(db, cap=10.0)
    strategy = _strategy(db, model, "fake-ab-bypass", policy)

    async def fake_submit_image_create(**kwargs):
        return {"stage_task_id": "should-not-submit"}

    monkeypatch.setattr(image_creation_service, "submit_image_create", fake_submit_image_create)

    with pytest.raises(HTTPException) as exc:
        await image_creation_service.create_image_task(
            db,
            {
                "mode": "text_to_image",
                "prompt": "A clean storyboard frame",
                "destination_role": "storyboard_first_frame",
                "strategy_id": strategy.id,
                "strategy_version": strategy.version,
                "count": 1,
                "cost_confirmation": True,
                "ab_test_group_id": "not-a-real-ab-group",
                "selection_preview_request_hash": "fake-preview-hash",
                "idempotency_key": "fake-ab-bypass-task",
                "user_id": "test-user-id",
            },
        )

    _assert_image_error(exc, 409, "IMAGE_COST_CONFIRMATION_PREVIEW_REQUIRED")


@pytest.mark.asyncio
async def test_create_image_task_rejects_existing_ab_group_without_matching_attempt_preview_hash(db, monkeypatch):
    model = _model(db)
    policy = _cost_policy(db, cap=10.0)
    strategy = _strategy(db, model, "ab-no-matching-attempt", policy)
    group = ImageProductionAbGroup(
        user_id="test-user-id",
        idempotency_key="existing-ab-no-attempt",
        source_request_hash="existing-preview-hash",
        prompt_snapshot_json={},
        cost_confirmation_json={"confirmed": True},
        status="running",
    )
    db.add(group)
    db.commit()

    async def fake_submit_image_create(**kwargs):
        raise AssertionError("A/B hash bypass must not submit without matching attempt")

    monkeypatch.setattr(image_creation_service, "submit_image_create", fake_submit_image_create)

    with pytest.raises(HTTPException) as exc:
        await image_creation_service.create_image_task(
            db,
            {
                "mode": "text_to_image",
                "prompt": "A clean storyboard frame",
                "destination_role": "storyboard_first_frame",
                "strategy_id": strategy.id,
                "strategy_version": strategy.version,
                "count": 1,
                "cost_confirmation": True,
                "ab_test_group_id": group.id,
                "selection_preview_request_hash": "not-an-attempt-preview-hash",
                "idempotency_key": "existing-ab-no-attempt-task",
                "user_id": "test-user-id",
            },
        )

    _assert_image_error(exc, 409, "IMAGE_COST_CONFIRMATION_PREVIEW_REQUIRED")


@pytest.mark.asyncio
async def test_create_image_task_rejects_owned_ab_group_hash_confirmation_without_user_id(db, monkeypatch):
    model = _model(db)
    policy = _cost_policy(db, cap=10.0)
    strategy = _strategy(db, model, "ab-owned-no-user", policy)
    group = ImageProductionAbGroup(
        user_id="test-user-id",
        idempotency_key="owned-ab-no-user",
        source_request_hash="owned-preview-hash",
        prompt_snapshot_json={},
        cost_confirmation_json={"confirmed": True},
        status="running",
    )
    db.add(group)
    db.flush()
    attempt = ImageProductionAbAttempt(
        group_id=group.id,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id=strategy.default_model_id,
        status="creating",
        metrics_snapshot_json={"selection_preview_request_hash": "owned-attempt-preview-hash"},
    )
    db.add(attempt)
    db.commit()

    async def fake_submit_image_create(**kwargs):
        raise AssertionError("A/B hash bypass must not submit without user ownership")

    monkeypatch.setattr(image_creation_service, "submit_image_create", fake_submit_image_create)

    with pytest.raises(HTTPException) as exc:
        await image_creation_service.create_image_task(
            db,
            {
                "mode": "text_to_image",
                "prompt": "A clean storyboard frame",
                "destination_role": "storyboard_first_frame",
                "strategy_id": strategy.id,
                "strategy_version": strategy.version,
                "count": 1,
                "cost_confirmation": True,
                "ab_test_group_id": group.id,
                "selection_preview_request_hash": "owned-attempt-preview-hash",
                "idempotency_key": "owned-ab-no-user-task",
            },
        )

    _assert_image_error(exc, 409, "IMAGE_COST_CONFIRMATION_PREVIEW_REQUIRED")


@pytest.mark.asyncio
async def test_create_image_task_rejects_anonymous_ab_group_hash_confirmation_with_user_id(db, monkeypatch):
    model = _model(db)
    policy = _cost_policy(db, cap=10.0)
    strategy = _strategy(db, model, "ab-anonymous-with-user", policy)
    group = ImageProductionAbGroup(
        user_id=None,
        idempotency_key="anonymous-ab-with-user",
        source_request_hash="anonymous-preview-hash",
        prompt_snapshot_json={},
        cost_confirmation_json={"confirmed": True},
        status="running",
    )
    db.add(group)
    db.flush()
    payload = {
        "mode": "text_to_image",
        "prompt": "A clean storyboard frame",
        "destination_role": "storyboard_first_frame",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "model_id": strategy.default_model_id,
        "count": 1,
        "cost_confirmation": True,
        "ab_test_group_id": group.id,
        "selection_preview_request_hash": "anonymous-attempt-preview-hash",
        "idempotency_key": "anonymous-ab-with-user-task",
        "user_id": "test-user-id",
    }
    hash_payload = dict(payload)
    image_creation_service._apply_strategy_defaults(hash_payload, strategy)
    image_creation_service._resolve_source_asset(db, hash_payload)
    image_creation_service._resolve_reference_images(db, hash_payload)
    attempt = ImageProductionAbAttempt(
        group_id=group.id,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id=strategy.default_model_id,
        status="creating",
        metrics_snapshot_json={
            "selection_preview_request_hash": "anonymous-attempt-preview-hash",
            "ab_attempt_request_hash": image_creation_service.normalized_request_hash(hash_payload),
            "ab_attempt_idempotency_key": "anonymous-ab-with-user-task",
        },
    )
    db.add(attempt)
    db.commit()

    async def fake_submit_image_create(**kwargs):
        raise AssertionError("A/B hash bypass must not submit across anonymous/user ownership")

    monkeypatch.setattr(image_creation_service, "submit_image_create", fake_submit_image_create)

    with pytest.raises(HTTPException) as exc:
        await image_creation_service.create_image_task(db, payload)

    _assert_image_error(exc, 409, "IMAGE_COST_CONFIRMATION_PREVIEW_REQUIRED")


@pytest.mark.asyncio
async def test_create_image_task_rejects_ab_hash_confirmation_when_task_payload_changes(db, monkeypatch):
    model = _model(db)
    policy = _cost_policy(db, cap=10.0)
    strategy = _strategy(db, model, "ab-hash-payload-change", policy)
    group = ImageProductionAbGroup(
        user_id="test-user-id",
        idempotency_key="ab-hash-payload-change",
        source_request_hash="ab-preview-hash",
        prompt_snapshot_json={},
        cost_confirmation_json={"confirmed": True},
        status="running",
    )
    db.add(group)
    db.flush()
    original_payload = {
        "mode": "text_to_image",
        "prompt": "Original storyboard frame",
        "destination_role": "storyboard_first_frame",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "model_id": strategy.default_model_id,
        "provider_options": {},
        "count": 1,
        "cost_confirmation": True,
        "ab_test_group_id": group.id,
        "selection_preview_request_hash": "attempt-preview-hash",
        "idempotency_key": "original-attempt-task",
        "user_id": "test-user-id",
    }
    attempt = ImageProductionAbAttempt(
        group_id=group.id,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id=strategy.default_model_id,
        status="creating",
        metrics_snapshot_json={
            "selection_preview_request_hash": "attempt-preview-hash",
            "ab_attempt_request_hash": image_creation_service.normalized_request_hash(original_payload),
        },
    )
    db.add(attempt)
    db.commit()

    async def fake_submit_image_create(**kwargs):
        return {"stage_task_id": "should-not-submit-changed-payload"}

    monkeypatch.setattr(image_creation_service, "submit_image_create", fake_submit_image_create)

    with pytest.raises(HTTPException) as exc:
        await image_creation_service.create_image_task(
            db,
            {**original_payload, "prompt": "Changed storyboard frame", "idempotency_key": "changed-attempt-task"},
        )

    _assert_image_error(exc, 409, "IMAGE_COST_CONFIRMATION_PREVIEW_REQUIRED")


def test_resolve_source_asset_rejects_asset_owned_by_another_user(db):
    task = _task(db, user_id="asset-owner")
    asset = _image_asset(db, task, user_id="asset-owner")
    payload = {"source_asset_id": asset.id, "user_id": "other-user"}

    with pytest.raises(HTTPException) as exc:
        image_creation_service._resolve_source_asset(db, payload)

    _assert_image_error(exc, 404, "SOURCE_ASSET_NOT_FOUND")
    assert asset.id not in exc.value.detail.get("affected_ids", [])


def test_resolve_reference_asset_rejects_asset_owned_by_another_user(db):
    task = _task(db, user_id="asset-owner")
    asset = _image_asset(db, task, user_id="asset-owner")
    payload = {"reference_images": [{"asset_id": asset.id}], "user_id": "other-user"}

    with pytest.raises(HTTPException) as exc:
        image_creation_service._resolve_reference_images(db, payload)

    _assert_image_error(exc, 404, "REFERENCE_ASSET_NOT_FOUND")
    assert asset.id not in exc.value.detail.get("affected_ids", [])


def test_resolve_source_asset_rejects_owned_asset_when_user_id_missing(db):
    task = _task(db, user_id="asset-owner")
    asset = _image_asset(db, task, user_id="asset-owner")
    payload = {"source_asset_id": asset.id}

    with pytest.raises(HTTPException) as exc:
        image_creation_service._resolve_source_asset(db, payload)

    _assert_image_error(exc, 404, "SOURCE_ASSET_NOT_FOUND")
    assert asset.id not in exc.value.detail.get("affected_ids", [])


def test_resolve_reference_asset_rejects_owned_asset_when_user_id_missing(db):
    task = _task(db, user_id="asset-owner")
    asset = _image_asset(db, task, user_id="asset-owner")
    payload = {"reference_images": [{"asset_id": asset.id}]}

    with pytest.raises(HTTPException) as exc:
        image_creation_service._resolve_reference_images(db, payload)

    _assert_image_error(exc, 404, "REFERENCE_ASSET_NOT_FOUND")
    assert asset.id not in exc.value.detail.get("affected_ids", [])


def test_resolve_source_asset_allows_asset_owned_by_same_user(db):
    task = _task(db, user_id="asset-owner")
    asset = _image_asset(db, task, user_id="asset-owner")
    payload = {"source_asset_id": asset.id, "user_id": "asset-owner"}

    source = image_creation_service._resolve_source_asset(db, payload)

    assert source["asset_id"] == asset.id
    assert source["url"] == asset.url
    assert payload["source_url"] == asset.url


@pytest.mark.asyncio
async def test_create_image_task_rejects_cross_user_idempotency_reuse_without_leaking_task_id(db):
    payload = {
        "mode": "text_to_image",
        "prompt": "A clean storyboard frame",
        "count": 1,
        "idempotency_key": "shared-image-task-key",
        "user_id": "user-b",
    }
    existing = _task(db, status="queued", idempotency_key="shared-image-task-key", user_id="user-a")
    existing.request_hash = image_creation_service.normalized_request_hash(payload)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        await image_creation_service.create_image_task(db, payload)

    _assert_image_error(exc, 409, "IMAGE_TASK_CONFLICT")
    assert existing.id not in exc.value.detail.get("affected_ids", [])


@pytest.mark.asyncio
async def test_create_image_task_rejects_missing_user_idempotency_reuse_for_owned_task(db):
    payload = {
        "mode": "text_to_image",
        "prompt": "A clean storyboard frame",
        "count": 1,
        "idempotency_key": "owned-image-task-key",
    }
    existing = _task(db, status="queued", idempotency_key="owned-image-task-key", user_id="user-a")
    existing.request_hash = image_creation_service.normalized_request_hash(payload)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        await image_creation_service.create_image_task(db, payload)

    _assert_image_error(exc, 409, "IMAGE_TASK_CONFLICT")
    assert existing.id not in exc.value.detail.get("affected_ids", [])


@pytest.mark.asyncio
async def test_create_image_task_rejects_authenticated_reuse_of_anonymous_task_idempotency(db):
    payload = {
        "mode": "text_to_image",
        "prompt": "A clean storyboard frame",
        "count": 1,
        "idempotency_key": "anonymous-image-task-key",
        "user_id": "user-a",
    }
    existing = _task(db, status="queued", idempotency_key="anonymous-image-task-key", user_id=None)
    existing.request_hash = image_creation_service.normalized_request_hash(payload)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        await image_creation_service.create_image_task(db, payload)

    _assert_image_error(exc, 409, "IMAGE_TASK_CONFLICT")
    assert existing.id not in exc.value.detail.get("affected_ids", [])


@pytest.mark.asyncio
async def test_create_image_task_idempotent_retry_ignores_expired_selection_preview(db):
    _model(db)
    preview = ImageSelectionPreview(
        user_id="test-user-id",
        mode="text_to_image",
        request_hash="expired-selection-preview-hash",
        response_json={},
        expires_at=image_creation_service.bj_now() - timedelta(minutes=1),
    )
    db.add(preview)
    db.commit()
    payload = {
        "mode": "text_to_image",
        "prompt": "A clean storyboard frame",
        "count": 1,
        "idempotency_key": "expired-selection-preview-retry",
        "cost_confirmation": True,
        "selection_preview_id": preview.id,
        "selection_preview_request_hash": preview.request_hash,
        "user_id": "test-user-id",
    }
    existing = _task(
        db,
        status="queued",
        idempotency_key=payload["idempotency_key"],
        user_id="test-user-id",
    )
    hash_payload = dict(payload)
    image_creation_service._resolve_source_asset(db, hash_payload)
    image_creation_service._resolve_reference_images(db, hash_payload)
    existing.request_hash = image_creation_service.normalized_request_hash(hash_payload)
    db.commit()

    task = await image_creation_service.create_image_task(db, payload)

    assert task.id == existing.id
    assert task.idempotency_key == payload["idempotency_key"]


def test_image_task_integrity_recovery_rejects_owner_mismatch_without_affected_ids(db):
    payload = {
        "mode": "text_to_image",
        "prompt": "A clean storyboard frame",
        "count": 1,
        "idempotency_key": "flush-race-task-key",
        "user_id": "user-a",
    }
    existing = _task(db, status="queued", idempotency_key="flush-race-task-key", user_id=None)
    request_hash = image_creation_service.normalized_request_hash(payload)
    existing.request_hash = request_hash
    db.commit()

    with pytest.raises(HTTPException) as exc:
        image_creation_service._recover_task_idempotency_integrity_error(
            db,
            idempotency_key=payload["idempotency_key"],
            payload=payload,
            request_hash=request_hash,
            exc=IntegrityError("insert image_creation_tasks", {}, Exception("unique")),
        )

    _assert_image_error(exc, 409, "IMAGE_TASK_CONFLICT")
    assert existing.id not in exc.value.detail.get("affected_ids", [])


@pytest.mark.asyncio
async def test_create_image_task_rejects_ab_hash_confirmation_with_replayed_idempotency_key(db, monkeypatch):
    model = _model(db)
    policy = _cost_policy(db, cap=10.0)
    strategy = _strategy(db, model, "ab-replay-key", policy)
    group = ImageProductionAbGroup(
        user_id="test-user-id",
        idempotency_key="ab-replay-key",
        source_request_hash="ab-preview-hash",
        prompt_snapshot_json={},
        cost_confirmation_json={"confirmed": True},
        status="running",
    )
    db.add(group)
    db.flush()
    original_payload = {
        "mode": "text_to_image",
        "prompt": "Original storyboard frame",
        "destination_role": "storyboard_first_frame",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "model_id": strategy.default_model_id,
        "count": 1,
        "cost_confirmation": True,
        "ab_test_group_id": group.id,
        "selection_preview_request_hash": "attempt-preview-hash",
        "idempotency_key": "expected-attempt-key",
        "user_id": "test-user-id",
    }
    hash_payload = dict(original_payload)
    image_creation_service._apply_strategy_defaults(hash_payload, strategy)
    image_creation_service._resolve_source_asset(db, hash_payload)
    image_creation_service._resolve_reference_images(db, hash_payload)
    attempt = ImageProductionAbAttempt(
        group_id=group.id,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        model_id=strategy.default_model_id,
        status="creating",
        metrics_snapshot_json={
            "selection_preview_request_hash": "attempt-preview-hash",
            "ab_attempt_request_hash": image_creation_service.normalized_request_hash(hash_payload),
            "ab_attempt_idempotency_key": "expected-attempt-key",
        },
    )
    db.add(attempt)
    db.commit()

    async def fake_submit_image_create(**kwargs):
        return {"stage_task_id": "should-not-submit-replayed-key"}

    monkeypatch.setattr(image_creation_service, "submit_image_create", fake_submit_image_create)

    with pytest.raises(HTTPException) as exc:
        await image_creation_service.create_image_task(
            db,
            {**original_payload, "idempotency_key": "replayed-attempt-key"},
        )

    _assert_image_error(exc, 409, "IMAGE_COST_CONFIRMATION_PREVIEW_REQUIRED")


@pytest.mark.asyncio
async def test_create_ab_group_marks_foreign_reference_asset_validation_as_failed_attempt_after_group_start(db):
    model = _model(db)
    strategies = [_strategy(db, model, "foreign-ref-a"), _strategy(db, model, "foreign-ref-b")]
    foreign_task = _task(db, user_id="asset-owner")
    foreign_asset = _image_asset(db, foreign_task, user_id="asset-owner")
    payload = _payload(
        strategies,
        idempotency_key="foreign-reference-after-start",
        reference_images=[{"asset_id": foreign_asset.id}],
    )
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    group = await service.create_ab_group(db, payload, user_id="test-user-id")
    retried = await service.create_ab_group(db, payload, user_id="test-user-id")

    attempts = db.query(ImageProductionAbAttempt).filter_by(group_id=group.id).all()
    assert group.status == "failed"
    assert retried.id == group.id
    assert {attempt.status for attempt in attempts} == {"failed"}
    assert all((attempt.metrics_snapshot_json or {}).get("error_code") == "REFERENCE_ASSET_NOT_FOUND" for attempt in attempts)


@pytest.mark.asyncio
async def test_create_ab_group_marks_image_task_http_exception_as_failed_attempt_after_group_start(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    calls = []

    async def fake_create_image_task(db_arg, task_payload):
        calls.append(task_payload)
        if len(calls) == 2:
            raise HTTPException(status_code=422, detail={"error_code": "IMAGE_MODE_UNSUPPORTED"})
        return _task(
            db,
            status="queued",
            strategy=strategies[0],
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="http-attempt-failure")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    group = await service.create_ab_group(db, payload, user_id="test-user-id")
    retried = await service.create_ab_group(db, payload, user_id="test-user-id")

    attempts = db.query(ImageProductionAbAttempt).filter_by(group_id=group.id).all()
    assert group.status == "partial_failed"
    assert retried.id == group.id
    assert {attempt.status for attempt in attempts} == {"creating", "failed"}
    assert db.query(ImageProductionAbGroup).filter_by(idempotency_key="http-attempt-failure").count() == 1


@pytest.mark.asyncio
async def test_create_ab_group_rejects_tampered_preview_hash_snapshot_before_side_effects(db):
    model = _model(db)
    strategies = [_strategy(db, model, "tamper-hash-a"), _strategy(db, model, "tamper-hash-b")]
    payload = _payload(strategies, idempotency_key="tamper-hash")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    event = _preview_event(db)
    event_payload = dict(event.payload_json)
    event_payload["previews"] = list(event_payload["previews"])
    event_payload["previews"][0] = {**event_payload["previews"][0], "request_hash": "tampered-preview-hash"}
    _set_preview_event_payload(db, event, event_payload)
    event_count = db.query(ProductionAuditEvent).count()

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, payload, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_PREVIEW_DRIFT")
    assert db.query(ProductionAuditEvent).count() == event_count
    assert db.query(ImageProductionAbGroup).count() == 0
    assert db.query(ImageProductionAbAttempt).count() == 0
    assert db.query(ImageCreationTask).count() == 0


@pytest.mark.asyncio
async def test_create_ab_group_rejects_hashless_stored_preview_before_side_effects(db):
    model = _model(db)
    strategies = [_strategy(db, model, "hashless-stored-a"), _strategy(db, model, "hashless-stored-b")]
    payload = _payload(strategies, idempotency_key="hashless-stored-preview")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    event = _preview_event(db)
    event_payload = dict(event.payload_json)
    event_payload["preview_hashes"] = list(event_payload["preview_hashes"])
    event_payload["previews"] = list(event_payload["previews"])
    event_payload["preview_hashes"][0] = None
    event_payload["previews"][0] = {**event_payload["previews"][0], "request_hash": None}
    _set_preview_event_payload(db, event, event_payload)
    event_count = db.query(ProductionAuditEvent).count()

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, payload, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_PREVIEW_DRIFT")
    assert db.query(ProductionAuditEvent).count() == event_count
    assert db.query(ImageProductionAbGroup).count() == 0
    assert db.query(ImageProductionAbAttempt).count() == 0
    assert db.query(ImageCreationTask).count() == 0


@pytest.mark.asyncio
async def test_create_ab_group_rejects_tampered_preview_strategy_snapshot_before_side_effects(db):
    model = _model(db)
    strategies = [_strategy(db, model, "tamper-strategy-a"), _strategy(db, model, "tamper-strategy-b")]
    payload = _payload(strategies, idempotency_key="tamper-strategy")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    event = _preview_event(db)
    event_payload = dict(event.payload_json)
    event_payload["previews"] = list(event_payload["previews"])
    event_payload["previews"][0] = {**event_payload["previews"][0], "strategy_id": strategies[1].id}
    _set_preview_event_payload(db, event, event_payload)
    event_count = db.query(ProductionAuditEvent).count()

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, payload, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_PREVIEW_DRIFT")
    assert db.query(ProductionAuditEvent).count() == event_count
    assert db.query(ImageProductionAbGroup).count() == 0
    assert db.query(ImageProductionAbAttempt).count() == 0
    assert db.query(ImageCreationTask).count() == 0


@pytest.mark.asyncio
async def test_create_ab_group_rejects_tampered_preview_total_cost_before_side_effects(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "tamper-cost-a"), _strategy(db, model, "tamper-cost-b")]
    payload = _payload(strategies, idempotency_key="tamper-total-cost")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    event = _preview_event(db)
    event_payload = dict(event.payload_json)
    event_payload["total_cost_estimate"] = {
        **event_payload["total_cost_estimate"],
        "amount": 0,
        "cost_limit_exceeded": False,
    }
    _set_preview_event_payload(db, event, event_payload)
    event_count = db.query(ProductionAuditEvent).count()

    async def fail_create_image_task(db_arg, task_payload):
        raise AssertionError("tampered total cost must be rejected before task creation")

    monkeypatch.setattr(service, "create_image_task", fail_create_image_task)

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, payload, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_PREVIEW_DRIFT")
    assert db.query(ProductionAuditEvent).count() == event_count
    assert db.query(ImageProductionAbGroup).count() == 0
    assert db.query(ImageProductionAbAttempt).count() == 0
    assert db.query(ImageCreationTask).count() == 0


@pytest.mark.asyncio
async def test_create_ab_group_rejects_malformed_preview_strategy_version_before_side_effects(db):
    model = _model(db)
    strategies = [_strategy(db, model, "malformed-version-a"), _strategy(db, model, "malformed-version-b")]
    payload = _payload(strategies, idempotency_key="malformed-strategy-version")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    event = _preview_event(db)
    event_payload = dict(event.payload_json)
    event_payload["previews"] = list(event_payload["previews"])
    event_payload["previews"][0] = {**event_payload["previews"][0], "strategy_version": "not-a-number"}
    _set_preview_event_payload(db, event, event_payload)
    event_count = db.query(ProductionAuditEvent).count()

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, payload, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_PREVIEW_DRIFT")
    assert db.query(ProductionAuditEvent).count() == event_count
    assert db.query(ImageProductionAbGroup).count() == 0
    assert db.query(ImageProductionAbAttempt).count() == 0
    assert db.query(ImageCreationTask).count() == 0


@pytest.mark.asyncio
async def test_create_ab_group_rejects_preview_user_mismatch_before_side_effects(db):
    model = _model(db)
    strategies = [_strategy(db, model, "user-mismatch-a"), _strategy(db, model, "user-mismatch-b")]
    payload = _payload(strategies, idempotency_key="user-mismatch")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="preview-user")["request_hash"]
    event_count = db.query(ProductionAuditEvent).count()

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, payload, user_id="other-user")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_PREVIEW_DRIFT")
    assert db.query(ProductionAuditEvent).count() == event_count
    assert db.query(ImageProductionAbGroup).count() == 0


@pytest.mark.asyncio
async def test_create_ab_group_rejects_expired_preview_snapshot_before_side_effects(db):
    model = _model(db)
    strategies = [_strategy(db, model, "expired-a"), _strategy(db, model, "expired-b")]
    payload = _payload(strategies, idempotency_key="expired-preview")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]
    event = _preview_event(db)
    event_payload = dict(event.payload_json)
    event_payload["previews"] = [
        {**preview, "expires_at": "2000-01-01T00:00:00"}
        for preview in event_payload["previews"]
    ]
    _set_preview_event_payload(db, event, event_payload)
    event_count = db.query(ProductionAuditEvent).count()

    with pytest.raises(HTTPException) as exc:
        await service.create_ab_group(db, payload, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_PREVIEW_DRIFT")
    assert db.query(ProductionAuditEvent).count() == event_count
    assert db.query(ImageProductionAbGroup).count() == 0


@pytest.mark.asyncio
async def test_create_ab_group_marks_post_persist_provider_http_failure_as_failed_attempt(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "provider-a"), _strategy(db, model, "provider-b")]
    calls = []

    async def fake_submit_image_create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise RuntimeError("provider unavailable after task snapshot")
        return {"stage_task_id": f"stage-task-{len(calls)}"}

    monkeypatch.setattr(image_creation_service, "submit_image_create", fake_submit_image_create)
    payload = _payload(strategies, idempotency_key="post-persist-provider-failure")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    group = await service.create_ab_group(db, payload, user_id="test-user-id")

    attempts = db.query(ImageProductionAbAttempt).filter_by(group_id=group.id).order_by(ImageProductionAbAttempt.created_at.asc()).all()
    assert group.status == "partial_failed"
    assert [attempt.status for attempt in attempts] == ["creating", "failed"]
    assert attempts[1].task_id
    failed_task = db.query(ImageCreationTask).filter_by(id=attempts[1].task_id).one()
    assert failed_task.status == "failed"
    retried = await service.create_ab_group(db, payload, user_id="test-user-id")
    assert retried.id == group.id


@pytest.mark.asyncio
async def test_create_ab_group_records_partial_failure_when_one_attempt_fails(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    calls = []

    async def fake_create_image_task(db_arg, task_payload):
        calls.append(task_payload)
        if len(calls) == 2:
            raise RuntimeError("provider unavailable")
        return _task(
            db,
            status="queued",
            strategy=strategies[0],
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="partial-failure")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    group = await service.create_ab_group(db, payload, user_id="test-user-id")

    attempts = db.query(ImageProductionAbAttempt).filter_by(group_id=group.id).all()
    assert group.status == "partial_failed"
    assert {attempt.status for attempt in attempts} == {"creating", "failed"}


@pytest.mark.asyncio
async def test_create_ab_group_redacts_runtime_error_metrics(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "redact-runtime-a"), _strategy(db, model, "redact-runtime-b")]
    calls = []

    async def fake_create_image_task(db_arg, task_payload):
        calls.append(task_payload)
        if len(calls) == 2:
            raise RuntimeError("provider failed api_key=super-secret Authorization: Bearer raw-token token=hidden")
        return _task(
            db,
            status="queued",
            strategy=strategies[0],
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="redact-runtime-error")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    group = await service.create_ab_group(db, payload, user_id="test-user-id")
    serialized = service.serialize_ab_group(db, group)

    failed = next(attempt for attempt in serialized["attempts"] if attempt["status"] == "failed")
    error = failed["metrics_snapshot"]["error"]
    assert "super-secret" not in error
    assert "raw-token" not in error
    assert "hidden" not in error
    assert "[REDACTED]" in error


def test_refresh_ab_group_marks_completed_when_all_attempts_terminal(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, _attempts = _group_with_attempts(db, strategies, task_status="completed", approved=False)

    refreshed = service.refresh_ab_group(db, group.id, user_id="test-user-id")

    assert refreshed.status == "completed"


def test_refresh_ab_group_marks_failed_when_all_attempts_failed(db):
    model = _model(db)
    strategies = [_strategy(db, model, "failed-a"), _strategy(db, model, "failed-b")]
    group, _attempts = _group_with_attempts(db, strategies, task_status="failed", approved=False)
    group.status = "running"
    db.commit()

    refreshed = service.refresh_ab_group(db, group.id, user_id="test-user-id")

    assert refreshed.status == "failed"


def test_refresh_ab_group_preserves_attempt_hash_binding_metrics(db):
    model = _model(db)
    strategies = [_strategy(db, model, "preserve-binding-a"), _strategy(db, model, "preserve-binding-b")]
    group, attempts = _group_with_attempts(db, strategies, task_status="completed", approved=False)
    attempts[0].metrics_snapshot_json = {
        "selection_preview_request_hash": "selection-hash",
        "ab_attempt_request_hash": "attempt-request-hash",
        "old_value": "replaceable",
    }
    db.commit()

    service.refresh_ab_group(db, group.id, user_id="test-user-id")

    refreshed_attempt = db.query(ImageProductionAbAttempt).filter_by(id=attempts[0].id).one()
    assert refreshed_attempt.metrics_snapshot_json["selection_preview_request_hash"] == "selection-hash"
    assert refreshed_attempt.metrics_snapshot_json["ab_attempt_request_hash"] == "attempt-request-hash"
    assert "estimated_cost" in refreshed_attempt.metrics_snapshot_json
    assert "metrics" in refreshed_attempt.metrics_snapshot_json


def test_refresh_ab_group_does_not_change_no_winner_decision(db):
    model = _model(db)
    strategies = [_strategy(db, model, "refresh-no-winner-a"), _strategy(db, model, "refresh-no-winner-b")]
    group, attempts = _group_with_attempts(db, strategies, task_status="failed", approved=False)
    group.status = "no_winner"
    group.decision_json = {"reason": "no usable result", "evidence_snapshot": {"decision": "no_winner"}}
    for attempt in attempts:
        task = db.query(ImageCreationTask).filter_by(id=attempt.task_id).one()
        task.status = "completed"
    db.commit()

    refreshed = service.refresh_ab_group(db, group.id, user_id="test-user-id")

    assert refreshed.status == "no_winner"
    assert refreshed.decision_json["reason"] == "no usable result"


def test_refresh_ab_group_does_not_overwrite_stale_decision_json_or_allow_second_decision(db):
    model = _model(db)
    strategies = [_strategy(db, model, "refresh-stale-decision-a"), _strategy(db, model, "refresh-stale-decision-b")]
    group, _attempts = _group_with_attempts(db, strategies, task_status="completed", approved=False)
    group.status = "running"
    group.decision_json = {"reason": "already decided", "evidence_snapshot": {"decision": "no_winner"}}
    db.commit()

    refreshed = service.refresh_ab_group(db, group.id, user_id="test-user-id")

    assert refreshed.status == "running"
    assert refreshed.decision_json["reason"] == "already decided"
    with pytest.raises(HTTPException) as exc:
        service.mark_ab_no_winner(db, group.id, {"reason": "second decision"}, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_WINNER_CONFLICT")
    saved = db.query(ImageProductionAbGroup).filter_by(id=group.id).one()
    assert saved.status == "running"
    assert saved.decision_json["reason"] == "already decided"


def test_refresh_ab_group_rejects_wrong_user_without_mutating_group(db):
    model = _model(db)
    strategies = [_strategy(db, model, "refresh-owner-a"), _strategy(db, model, "refresh-owner-b")]
    group, _attempts = _group_with_attempts(db, strategies, task_status="completed", approved=False)

    with pytest.raises(HTTPException) as exc:
        service.refresh_ab_group(db, group.id, user_id="other-user")

    _assert_image_error(exc, 404, "IMAGE_AB_TEST_GROUP_NOT_FOUND")
    saved = db.query(ImageProductionAbGroup).filter_by(id=group.id).one()
    assert saved.status == "completed"


def test_refresh_ab_group_rejects_missing_user_without_mutating_owned_group(db):
    model = _model(db)
    strategies = [_strategy(db, model, "refresh-missing-user-a"), _strategy(db, model, "refresh-missing-user-b")]
    group, _attempts = _group_with_attempts(db, strategies, task_status="completed", approved=False)

    with pytest.raises(HTTPException) as exc:
        service.refresh_ab_group(db, group.id)

    _assert_image_error(exc, 404, "IMAGE_AB_TEST_GROUP_NOT_FOUND")
    saved = db.query(ImageProductionAbGroup).filter_by(id=group.id).one()
    assert saved.status == "completed"


def test_adopt_ab_winner_requires_approved_asset(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, attempts = _group_with_attempts(db, strategies, task_status="completed", approved=False)

    with pytest.raises(HTTPException) as exc:
        service.adopt_ab_winner(db, group.id, attempts[0].id, {"reason": "best composition"}, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_ATTEMPT_NOT_READY")


def test_adopt_ab_winner_records_decision_for_approved_attempt(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, attempts = _group_with_attempts(db, strategies, task_status="completed", approved=True)

    updated = service.adopt_ab_winner(
        db,
        group.id,
        attempts[0].id,
        {"reason": "approved winner", "notes": "Use this frame"},
        user_id="test-user-id",
    )

    assert updated.status == "winner_selected"
    assert updated.winner_attempt_id == attempts[0].id
    assert updated.decision_json["reason"] == "approved winner"
    assert updated.decision_json["evidence_snapshot"]["winner_attempt_id"] == attempts[0].id


def test_adopt_ab_winner_rejects_wrong_user_without_mutating_group(db):
    model = _model(db)
    strategies = [_strategy(db, model, "winner-owner-a"), _strategy(db, model, "winner-owner-b")]
    group, attempts = _group_with_attempts(db, strategies, task_status="completed", approved=True)

    with pytest.raises(HTTPException) as exc:
        service.adopt_ab_winner(db, group.id, attempts[0].id, {"reason": "wrong user"}, user_id="other-user")

    _assert_image_error(exc, 404, "IMAGE_AB_TEST_GROUP_NOT_FOUND")
    saved = db.query(ImageProductionAbGroup).filter_by(id=group.id).one()
    assert saved.status == "completed"
    assert saved.winner_attempt_id is None
    assert db.query(ProductionAuditEvent).filter_by(event_type="image_ab.winner").count() == 0


def test_adopt_ab_winner_rejects_missing_user_without_mutating_owned_group(db):
    model = _model(db)
    strategies = [_strategy(db, model, "winner-missing-user-a"), _strategy(db, model, "winner-missing-user-b")]
    group, attempts = _group_with_attempts(db, strategies, task_status="completed", approved=True)

    with pytest.raises(HTTPException) as exc:
        service.adopt_ab_winner(db, group.id, attempts[0].id, {"reason": "missing user"})

    _assert_image_error(exc, 404, "IMAGE_AB_TEST_GROUP_NOT_FOUND")
    saved = db.query(ImageProductionAbGroup).filter_by(id=group.id).one()
    assert saved.status == "completed"
    assert saved.winner_attempt_id is None
    assert db.query(ProductionAuditEvent).filter_by(event_type="image_ab.winner").count() == 0


def test_adopt_ab_winner_stores_decision_evidence_snapshot(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, attempts = _group_with_attempts(db, strategies, task_status="completed", approved=True)

    updated = service.adopt_ab_winner(
        db,
        group.id,
        attempts[0].id,
        {"reason": "face consistent"},
        user_id="test-user-id",
    )
    snapshot = updated.decision_json["evidence_snapshot"]

    assert len(snapshot["attempts"]) == 2
    assert snapshot["attempts"][0]["approved_asset_ready"] is True
    assert snapshot["attempts"][0]["approved_asset_ids"]


def test_adopt_ab_winner_conditional_update_detects_racing_decision(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "race-a"), _strategy(db, model, "race-b")]
    group, attempts = _group_with_attempts(db, strategies, task_status="completed", approved=True)
    original_snapshot = service._ab_decision_evidence_snapshot

    def racing_snapshot(db_arg, group_arg, winner_attempt_id, decision):
        db_arg.query(ImageProductionAbGroup).filter_by(id=group_arg.id).update(
            {"status": "no_winner", "decision_json": {"reason": "racing decision"}},
            synchronize_session=False,
        )
        db_arg.commit()
        return original_snapshot(db_arg, group_arg, winner_attempt_id, decision)

    monkeypatch.setattr(service, "_ab_decision_evidence_snapshot", racing_snapshot)

    with pytest.raises(HTTPException) as exc:
        service.adopt_ab_winner(db, group.id, attempts[0].id, {"reason": "late winner"}, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_WINNER_CONFLICT")
    saved = db.query(ImageProductionAbGroup).filter_by(id=group.id).one()
    assert saved.status == "no_winner"
    assert saved.decision_json["reason"] == "racing decision"
    assert db.query(ProductionAuditEvent).filter_by(event_type="image_ab.winner").count() == 0


def test_mark_ab_no_winner_stores_all_attempt_evidence(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, _attempts = _group_with_attempts(db, strategies, task_status="completed", approved=False)

    updated = service.mark_ab_no_winner(db, group.id, {"reason": "both off style"}, user_id="test-user-id")

    assert updated.status == "no_winner"
    assert updated.decision_json["reason"] == "both off style"
    assert updated.decision_json["evidence_snapshot"]["decision"] == "no_winner"
    assert len(updated.decision_json["evidence_snapshot"]["attempts"]) == 2


def test_mark_ab_no_winner_rejects_running_attempts_without_mutating_group(db):
    model = _model(db)
    strategies = [_strategy(db, model, "no-winner-running-a"), _strategy(db, model, "no-winner-running-b")]
    group, _attempts = _group_with_attempts(db, strategies, task_status="running", approved=False)
    group.status = "running"
    group.decision_json = {}
    db.commit()

    with pytest.raises(HTTPException) as exc:
        service.mark_ab_no_winner(db, group.id, {"reason": "not ready"}, user_id="test-user-id")

    _assert_image_error(exc, 409, "IMAGE_AB_TEST_ATTEMPT_NOT_READY")
    saved = db.query(ImageProductionAbGroup).filter_by(id=group.id).one()
    assert saved.status == "running"
    assert saved.decision_json == {}
    assert db.query(ProductionAuditEvent).filter_by(event_type="image_ab.no_winner").count() == 0


def test_mark_ab_no_winner_rejects_wrong_user_without_mutating_group(db):
    model = _model(db)
    strategies = [_strategy(db, model, "no-winner-owner-a"), _strategy(db, model, "no-winner-owner-b")]
    group, _attempts = _group_with_attempts(db, strategies, task_status="completed", approved=False)
    original_decision = group.decision_json

    with pytest.raises(HTTPException) as exc:
        service.mark_ab_no_winner(db, group.id, {"reason": "wrong user"}, user_id="other-user")

    _assert_image_error(exc, 404, "IMAGE_AB_TEST_GROUP_NOT_FOUND")
    saved = db.query(ImageProductionAbGroup).filter_by(id=group.id).one()
    assert saved.status == "completed"
    assert saved.decision_json == original_decision
    assert db.query(ProductionAuditEvent).filter_by(event_type="image_ab.no_winner").count() == 0


def test_mark_ab_no_winner_rejects_missing_user_without_mutating_owned_group(db):
    model = _model(db)
    strategies = [_strategy(db, model, "no-winner-missing-user-a"), _strategy(db, model, "no-winner-missing-user-b")]
    group, _attempts = _group_with_attempts(db, strategies, task_status="completed", approved=False)
    original_decision = group.decision_json

    with pytest.raises(HTTPException) as exc:
        service.mark_ab_no_winner(db, group.id, {"reason": "missing user"})

    _assert_image_error(exc, 404, "IMAGE_AB_TEST_GROUP_NOT_FOUND")
    saved = db.query(ImageProductionAbGroup).filter_by(id=group.id).one()
    assert saved.status == "completed"
    assert saved.decision_json == original_decision
    assert db.query(ProductionAuditEvent).filter_by(event_type="image_ab.no_winner").count() == 0


def test_serialize_ab_group_includes_attempt_task_status_and_approved_asset_ready(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, attempts = _group_with_attempts(db, strategies, task_status="completed", approved=True)
    attempts[1].task_id = None
    db.commit()

    payload = service.serialize_ab_group(db, group)

    assert payload["attempts"][0]["task_status"] == "completed"
    assert payload["attempts"][0]["approved_asset_ready"] is True
    assert payload["attempts"][1]["task_status"] is None
    assert payload["attempts"][1]["approved_asset_ready"] is False


def test_preview_ab_group_records_audit_event(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]

    service.preview_ab_group(db, _payload(strategies), user_id="test-user-id")

    event = db.query(ProductionAuditEvent).filter_by(event_type="image_ab.preview").one()
    assert event.payload_json["scope"] == "image_ab"


@pytest.mark.asyncio
async def test_create_ab_group_records_create_and_partial_failure_events(db, monkeypatch):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    calls = []

    async def fake_create_image_task(db_arg, task_payload):
        calls.append(task_payload)
        if len(calls) == 2:
            raise HTTPException(status_code=502, detail={"error_code": "IMAGE_PROVIDER_UNAVAILABLE"})
        return _task(
            db,
            status="queued",
            strategy=strategies[0],
            idempotency_key=task_payload["idempotency_key"],
            ab_group_id=task_payload["ab_test_group_id"],
        )

    monkeypatch.setattr(service, "create_image_task", fake_create_image_task)
    payload = _payload(strategies, idempotency_key="audit-partial")
    payload["preview_request_hash"] = service.preview_ab_group(db, payload, user_id="test-user-id")["request_hash"]

    await service.create_ab_group(db, payload, user_id="test-user-id")

    event_types = {row.event_type for row in db.query(ProductionAuditEvent).all()}
    assert {"image_ab.preview", "image_ab.create", "image_ab.partial_failed"}.issubset(event_types)
    create_payload = db.query(ProductionAuditEvent).filter_by(event_type="image_ab.create").one().payload_json
    partial_payload = db.query(ProductionAuditEvent).filter_by(event_type="image_ab.partial_failed").one().payload_json
    for event_payload in (create_payload, partial_payload):
        assert event_payload["scope"] == "image_ab"
        assert event_payload["group_id"]
        assert event_payload["status"] == "partial_failed"
        assert event_payload["strategy_count"] == 2
        assert event_payload["total_cost_estimate"]["amount"] == 3.0
        assert len(event_payload["attempts"]) == 2
        assert {"attempt_id", "status", "task_id", "strategy_id"}.issubset(event_payload["attempts"][0])
        failed_attempt = next(attempt for attempt in event_payload["attempts"] if attempt["status"] == "failed")
        assert failed_attempt["error_code"] == "IMAGE_PROVIDER_UNAVAILABLE"
    assert partial_payload["failure_count"] == 1
    assert partial_payload["success_count"] == 1


def test_adopt_ab_winner_records_audit_event(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, attempts = _group_with_attempts(db, strategies, task_status="completed", approved=True)
    group.cost_confirmation_json = {"total_cost_estimate": {"amount": 3.0, "currency": "CNY"}}
    db.commit()

    service.adopt_ab_winner(
        db,
        group.id,
        attempts[0].id,
        {"reason": "winner", "notes": "best composition"},
        user_id="test-user-id",
    )

    event = db.query(ProductionAuditEvent).filter_by(event_type="image_ab.winner").one()
    assert event.payload_json["scope"] == "image_ab"
    assert event.payload_json["group_id"] == group.id
    assert event.payload_json["status"] == "winner_selected"
    assert event.payload_json["winner_attempt_id"] == attempts[0].id
    assert event.payload_json["winner_asset_ids"]
    assert event.payload_json["strategy_count"] == 2
    assert event.payload_json["total_cost_estimate"]["amount"] == 3.0
    assert event.payload_json["decision_summary"] == {"reason": "winner", "notes": "best composition"}


def test_mark_ab_no_winner_records_audit_event(db):
    model = _model(db)
    strategies = [_strategy(db, model, "variant-a"), _strategy(db, model, "variant-b")]
    group, _attempts = _group_with_attempts(db, strategies, task_status="completed", approved=False)
    group.cost_confirmation_json = {"total_cost_estimate": {"amount": 3.0, "currency": "CNY"}}
    db.commit()

    service.mark_ab_no_winner(
        db,
        group.id,
        {"reason": "reject all", "notes": "style mismatch"},
        user_id="test-user-id",
    )

    event = db.query(ProductionAuditEvent).filter_by(event_type="image_ab.no_winner").one()
    assert event.payload_json["scope"] == "image_ab"
    assert event.payload_json["group_id"] == group.id
    assert event.payload_json["status"] == "no_winner"
    assert event.payload_json["strategy_count"] == 2
    assert event.payload_json["total_cost_estimate"]["amount"] == 3.0
    assert event.payload_json["decision_summary"] == {"reason": "reject all", "notes": "style mismatch"}
