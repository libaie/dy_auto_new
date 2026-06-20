from datetime import datetime

from fastapi.testclient import TestClient

from app.db.models import ImageProductionMetric, ImageProductionPolicyVersion, ImageProductionStrategy, ImageProductionStrategyVersion, ProductionAuditEvent
from app.deps import verify_admin_token
from app.main import app
from app.domains.image_generation.image_production_strategy_service import seed_default_image_strategies


client = TestClient(app)


def _strategy_payload(**overrides):
    payload = {
        "slug": "test-storyboard",
        "name": "Test Storyboard",
        "description": "For storyboard first frames.",
        "destination_role": "storyboard_first_frame",
        "supported_modes": ["text_to_image"],
        "default_model_id": None,
        "fallback_model_ids": [],
        "common_parameters": {"size": "1024x1024"},
        "provider_options": {},
    }
    payload.update(overrides)
    return payload


def _policy(db, policy_type="review", status="active"):
    policy = ImageProductionPolicyVersion(
        policy_type=policy_type,
        name=f"{policy_type}-policy",
        version=1,
        snapshot_json={},
        status=status,
    )
    db.add(policy)
    db.commit()
    return policy


def test_seed_default_image_strategies_is_idempotent(db):
    seed_default_image_strategies(db)
    seed_default_image_strategies(db)

    strategies = db.query(ImageProductionStrategy).order_by(ImageProductionStrategy.slug.asc()).all()

    assert [strategy.slug for strategy in strategies] == [
        "character-anchor-default",
        "image-to-video-input-default",
        "storyboard-first-frame-default",
    ]
    assert db.query(ImageProductionStrategyVersion).count() == 3


def test_create_strategy_writes_initial_version(db):
    resp = client.post("/api/image-production/strategies", json=_strategy_payload())

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["strategy"]["slug"] == "test-storyboard"
    assert body["strategy"]["version"] == 1
    assert db.query(ImageProductionStrategyVersion).count() == 1


def test_create_strategy_can_generate_slug_from_name():
    payload = _strategy_payload(slug=None, name="Auto Slug Strategy")

    resp = client.post("/api/image-production/strategies", json=payload)

    assert resp.status_code == 200
    assert resp.json()["strategy"]["slug"] == "auto-slug-strategy"


def test_update_strategy_requires_current_version():
    created = client.post(
        "/api/image-production/strategies",
        json=_strategy_payload(
            slug="conflict-test",
            name="Conflict Test",
            destination_role="image_to_video_input",
            supported_modes=["image_to_image"],
        ),
    ).json()["strategy"]

    conflict = client.put(
        f"/api/image-production/strategies/{created['id']}",
        json=_strategy_payload(
            slug="conflict-test",
            name="Stale Save",
            destination_role="image_to_video_input",
            supported_modes=["image_to_image"],
            version=created["version"] - 1,
        ),
    )

    assert conflict.status_code == 409
    assert conflict.json()["detail"]["error_code"] == "IMAGE_STRATEGY_VERSION_CONFLICT"


def test_update_strategy_maps_duplicate_version_to_conflict(db):
    created = client.post(
        "/api/image-production/strategies",
        json=_strategy_payload(
            slug="duplicate-version-test",
            name="Duplicate Version Test",
        ),
    ).json()["strategy"]
    db.add(ImageProductionStrategyVersion(strategy_id=created["id"], version=2, snapshot_json={}))
    db.commit()

    resp = client.put(
        f"/api/image-production/strategies/{created['id']}",
        json=_strategy_payload(
            slug="duplicate-version-test",
            name="Duplicate Version Test Updated",
            version=created["version"],
        ),
    )

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_STRATEGY_VERSION_CONFLICT"


def test_create_strategy_rejects_missing_policy_id():
    resp = client.post(
        "/api/image-production/strategies",
        json=_strategy_payload(review_policy_version_id="missing-policy-id"),
    )

    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "IMAGE_POLICY_VERSION_NOT_FOUND"


def test_create_strategy_rejects_wrong_policy_type(db):
    cost_policy = _policy(db, policy_type="cost")

    resp = client.post(
        "/api/image-production/strategies",
        json=_strategy_payload(review_policy_version_id=cost_policy.id),
    )

    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "IMAGE_POLICY_TYPE_INVALID"


def test_create_strategy_rejects_inactive_policy(db):
    review_policy = _policy(db, policy_type="review", status="archived")

    resp = client.post(
        "/api/image-production/strategies",
        json=_strategy_payload(review_policy_version_id=review_policy.id),
    )

    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "IMAGE_POLICY_VERSION_INACTIVE"


def test_strategy_reads_require_admin_role():
    created = client.post(
        "/api/image-production/strategies",
        json=_strategy_payload(slug="admin-read-test", name="Admin Read Test"),
    ).json()["strategy"]
    app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "operator")
    try:
        listed = client.get("/api/image-production/strategies")
        read = client.get(f"/api/image-production/strategies/{created['id']}")
    finally:
        app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "admin")

    assert listed.status_code == 403
    assert read.status_code == 403


def test_list_strategies_aggregates_metrics_across_model_rows(db):
    strategy = client.post(
        "/api/image-production/strategies",
        json=_strategy_payload(
            slug="aggregate-metrics-test",
            name="Aggregate Metrics Test",
            default_model_id=None,
        ),
    ).json()["strategy"]
    db.add_all([
        ImageProductionMetric(
            strategy_id=strategy["id"],
            strategy_version=strategy["version"],
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
            updated_at=datetime(2026, 5, 29, 10, 0, 0),
        ),
        ImageProductionMetric(
            strategy_id=strategy["id"],
            strategy_version=strategy["version"],
            model_id="model-b",
            attempt_count=3,
            success_count=3,
            failure_count=0,
            ai_pass_count=2,
            human_pass_count=1,
            repaint_count=0,
            average_latency_seconds=20,
            average_cost_amount=4,
            currency="CNY",
            updated_at=datetime(2026, 5, 29, 11, 0, 0),
        ),
        ImageProductionMetric(
            strategy_id=strategy["id"],
            strategy_version=strategy["version"] + 1,
            model_id="model-c",
            attempt_count=100,
            success_count=100,
            average_latency_seconds=100,
            average_cost_amount=100,
            currency="USD",
        ),
    ])
    db.commit()

    resp = client.get("/api/image-production/strategies?include_metrics=true")

    assert resp.status_code == 200
    listed = next(row for row in resp.json()["strategies"] if row["id"] == strategy["id"])
    assert listed["metrics"]["attempt_count"] == 5
    assert listed["metrics"]["success_count"] == 4
    assert listed["metrics"]["failure_count"] == 1
    assert listed["metrics"]["ai_pass_rate"] == 0.6
    assert listed["metrics"]["human_pass_rate"] == 0.2
    assert listed["metrics"]["repaint_count"] == 1
    assert listed["metrics"]["success_rate"] == 0.8
    assert listed["metrics"]["average_latency_seconds"] == 16
    assert listed["metrics"]["average_cost_amount"] == 3.2
    assert listed["metrics"]["currency"] == "CNY"
    assert listed["metrics"]["low_sample"] is False
    assert listed["metrics"]["updated_at"] == "2026-05-29T11:00:00"


def test_archive_and_activate_write_audit_events(db):
    strategy = client.post(
        "/api/image-production/strategies",
        json=_strategy_payload(
            slug="archive-test",
            name="Archive Test",
            destination_role="character_anchor_image",
            supported_modes=["text_to_image"],
        ),
    ).json()["strategy"]

    archived = client.post(f"/api/image-production/strategies/{strategy['id']}/archive")
    listed_after_archive = client.get("/api/image-production/strategies?status=active")
    activated = client.post(f"/api/image-production/strategies/{strategy['id']}/activate")
    listed_after_activate = client.get("/api/image-production/strategies?status=active")
    events = db.query(ProductionAuditEvent).order_by(ProductionAuditEvent.created_at.asc()).all()

    assert archived.status_code == 200
    assert all(row["id"] != strategy["id"] for row in listed_after_archive.json()["strategies"])
    assert activated.status_code == 200
    assert any(row["id"] == strategy["id"] for row in listed_after_activate.json()["strategies"])
    assert [event.event_type for event in events] == ["image_strategy.archived", "image_strategy.active"]
    assert events[0].payload_json["strategy_id"] == strategy["id"]
    assert events[0].payload_json["previous_status"] == "active"
    assert events[0].payload_json["next_status"] == "archived"
