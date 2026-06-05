from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db_models import (
    Episode,
    ImageCreationAsset,
    ImageCreationTask,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
)
from app.deps import verify_admin_token
from app.main import app
from app.services.image_asset_bridge_service import promote_image_asset_to_video_asset
from app.services.image_creation_service import asset_payload, review_image_asset


client = TestClient(app)


def _error_code(resp):
    detail = resp.json()["detail"]
    if isinstance(detail, dict):
        return detail.get("error_code")
    return detail


def _seed_run(db):
    series = Series(title="Bridge Series", logline="Bridge logline")
    db.add(series)
    db.commit()
    episode = Episode(series_id=series.id, episode_number=1, title="Bridge Episode")
    db.add(episode)
    db.commit()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_review_pending",
        current_stage="image_review",
    )
    db.add(run)
    db.commit()
    return run


def _seed_image_asset(db, status="approved"):
    suffix = uuid4().hex
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="completed",
        prompt="bridge source",
        provider="pixelle",
        model_id="seedream",
        pixelle_task_id=f"pixelle-task-{suffix}",
        strategy_id="strategy-1",
        strategy_version=2,
        strategy_snapshot_json={"slug": "strategy-one"},
    )
    db.add(task)
    db.commit()
    asset = ImageCreationAsset(
        task_id=task.id,
        asset_type="image",
        asset_kind="image",
        url=f"https://cdn.test/source-{suffix}.png",
        local_path="/tmp/source.png",
        thumbnail_url="https://cdn.test/source-thumb.png",
        width=1080,
        height=1920,
        checksum="sha256-source",
        size_bytes=12345,
        status=status,
        version=3,
        slot_key=f"frame-source-{suffix}",
        destination_role="image_to_video_input",
        destination_context_json={"video_run_id": "run-1", "frame_id": "frame-001", "shot": "opening"},
        provider="pixelle",
        model_id="seedream",
        provider_task_id=f"provider-task-{suffix}",
        pixelle_task_id=f"pixelle-task-{suffix}",
        audit_status="passed",
        ai_score=0.93,
        ai_report_json={"issues": []},
        manual_review_status="approved",
        metadata_json={"camera": "wide"},
    )
    db.add(asset)
    db.commit()
    return asset


def _seed_series_episode(db, title):
    series = Series(title=title, logline=f"{title} logline")
    db.add(series)
    db.commit()
    episode = Episode(series_id=series.id, episode_number=1, title=f"{title} Episode")
    db.add(episode)
    db.commit()
    return series, episode


def test_approved_image_asset_promotes_to_video_asset_and_records_usage(db):
    run = _seed_run(db)
    asset = _seed_image_asset(db, status="approved")

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={
            "run_id": run.id,
            "frame_id": "frame-001",
            "version": 3,
            "destination_role": "image_to_video_input",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    video_asset = body["video_asset"]
    assert video_asset["run_id"] == run.id
    assert video_asset["episode_id"] == run.episode_id
    assert video_asset["frame_id"] == "frame-001"
    assert video_asset["asset_type"] == "image"
    assert video_asset["stage"] == "image_review"
    assert video_asset["status"] == "approved"
    assert video_asset["url"] == asset.url
    assert video_asset["local_path"] == asset.local_path
    assert video_asset["thumbnail_url"] == asset.thumbnail_url
    assert video_asset["version"] == 3

    saved = db.query(VideoProductionAsset).filter_by(id=video_asset["id"]).one()
    assert saved.metadata_json["source_image_asset_id"] == asset.id
    assert saved.metadata_json["source_image_task_id"] == asset.task_id
    assert saved.metadata_json["source_image_version"] == asset.version
    assert saved.metadata_json["strategy_snapshot"] == {"slug": "strategy-one"}
    assert saved.metadata_json["source_image_asset"]["id"] == asset.id
    assert saved.metadata_json["source_image_task"]["id"] == asset.task_id
    assert saved.metadata_json["source_version"] == asset.version
    assert saved.metadata_json["destination_role"] == "image_to_video_input"
    assert saved.metadata_json["review_snapshot"]["status"] == "approved"
    assert saved.metadata_json["provider"] == "pixelle"
    assert saved.checksum == asset.checksum
    assert saved.size_bytes == asset.size_bytes
    assert saved.source_version == asset.version

    db.refresh(asset)
    assert asset.downstream_usage_json == [
        {
            "type": "video_production_asset",
            "run_id": run.id,
            "frame_id": "frame-001",
            "version": 3,
            "video_asset_id": saved.id,
        }
    ]


def test_non_approved_image_asset_is_blocked_by_review_gate(db):
    run = _seed_run(db)
    pending_asset = _seed_image_asset(db, status="review_pending")

    resp = client.post(
        f"/api/image-production/assets/{pending_asset.id}/promote-to-video-asset",
        json={"run_id": run.id, "frame_id": "frame-001", "version": 1},
    )

    assert resp.status_code == 409
    assert _error_code(resp) == "IMAGE_REVIEW_GATE_BLOCKED"
    assert db.query(VideoProductionAsset).count() == 0


def test_promote_blocks_manual_review_pending_asset(db):
    run = _seed_run(db)
    asset = _seed_image_asset(db, status="review_pending")
    task = db.query(ImageCreationTask).filter_by(id=asset.task_id).one()
    task.request_json = {
        "review_gate": {
            "required": True,
            "manual_required": True,
            "status": "manual_review_pending",
        }
    }
    asset.manual_review_status = "pending"
    asset.metadata_json = {
        "review_gate": {
            "required": True,
            "manual_required": True,
            "status": "manual_review_pending",
        }
    }
    db.commit()

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={"run_id": run.id, "frame_id": "frame-001", "version": 1},
    )

    detail = resp.json()["detail"]
    assert resp.status_code == 409
    assert detail["error_code"] == "IMAGE_REVIEW_GATE_BLOCKED"
    assert detail["rescue_actions"][0]["type"] == "manual_review_required"
    assert db.query(VideoProductionAsset).count() == 0


def test_promote_blocks_ai_review_pending_asset_even_when_manual_approved(db):
    run = _seed_run(db)
    asset = _seed_image_asset(db, status="approved")
    task = db.query(ImageCreationTask).filter_by(id=asset.task_id).one()
    gate = {
        "required": True,
        "manual_required": True,
        "ai_required": True,
        "status": "ai_review_pending",
    }
    task.request_json = {"review_gate": gate}
    asset.manual_review_status = "approved"
    asset.audit_status = "pending"
    asset.metadata_json = {"review_gate": gate}
    db.commit()

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={"run_id": run.id, "frame_id": "frame-001", "version": 1},
    )

    detail = resp.json()["detail"]
    assert resp.status_code == 409
    assert detail["error_code"] == "IMAGE_REVIEW_GATE_BLOCKED"
    assert detail["details"]["review_gate"]["status"] == "ai_review_pending"
    assert db.query(VideoProductionAsset).count() == 0


@pytest.mark.parametrize(
    ("asset_status", "destination_role", "metadata_json"),
    [
        ("rejected", "image_to_video_input", {"review_gate": {"required": False}}),
        ("blocked", "storyboard_frame", {}),
    ],
)
def test_promote_blocks_rejected_or_blocked_asset_even_without_required_review_gate(
    db,
    asset_status,
    destination_role,
    metadata_json,
):
    run = _seed_run(db)
    asset = _seed_image_asset(db, status=asset_status)
    asset.destination_role = destination_role
    asset.metadata_json = metadata_json
    db.commit()

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={"run_id": run.id, "frame_id": "frame-001", "version": 1},
    )

    detail = resp.json()["detail"]
    assert resp.status_code == 409
    assert detail["error_code"] == "IMAGE_REVIEW_GATE_BLOCKED"
    assert detail["details"]["review_gate"]["status"] == "blocked"
    assert detail["rescue_actions"]
    assert db.query(VideoProductionAsset).count() == 0


def test_promote_blocks_approved_asset_when_review_gate_status_blocked(db):
    run = _seed_run(db)
    asset = _seed_image_asset(db, status="approved")
    asset.manual_review_status = "approved"
    asset.audit_status = "approved"
    asset.metadata_json = {"review_gate": {"required": False, "status": "blocked"}}
    db.commit()

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={"run_id": run.id, "frame_id": "frame-001", "version": 1},
    )

    detail = resp.json()["detail"]
    assert resp.status_code == 409
    assert detail["error_code"] == "IMAGE_REVIEW_GATE_BLOCKED"
    assert detail["details"]["review_gate"]["status"] == "blocked"
    assert detail["rescue_actions"]
    assert db.query(VideoProductionAsset).count() == 0


def test_promote_blocks_review_pending_asset_even_when_review_gate_not_required(db):
    run = _seed_run(db)
    asset = _seed_image_asset(db, status="review_pending")
    asset.metadata_json = {"review_gate": {"required": False}}
    db.commit()

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={"run_id": run.id, "frame_id": "frame-001", "version": 1},
    )

    detail = resp.json()["detail"]
    assert resp.status_code == 409
    assert detail["error_code"] == "IMAGE_REVIEW_GATE_BLOCKED"
    assert detail["rescue_actions"]
    assert db.query(VideoProductionAsset).count() == 0


def test_manual_approve_does_not_unblock_blocked_review_gate(db):
    run = _seed_run(db)
    asset = _seed_image_asset(db, status="review_pending")
    asset.manual_review_status = "pending"
    asset.audit_status = "approved"
    asset.metadata_json = {
        "review_gate": {
            "required": True,
            "manual_required": True,
            "status": "blocked",
        }
    }
    db.commit()

    reviewed, _ = review_image_asset(db, asset.id, "approve", asset_version=asset.version)

    assert reviewed.metadata_json["review_gate"]["status"] == "blocked"
    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={"run_id": run.id, "frame_id": "frame-001", "version": 1},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_REVIEW_GATE_BLOCKED"


def test_legacy_approved_image_to_video_asset_without_review_gate_can_promote(db):
    run = _seed_run(db)
    asset = _seed_image_asset(db, status="approved")
    asset.destination_role = "image_to_video_input"
    asset.manual_review_status = None
    asset.audit_status = None
    asset.metadata_json = {"camera": "legacy"}
    db.commit()

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={"run_id": run.id, "frame_id": "frame-legacy", "version": 1},
    )

    assert resp.status_code == 200
    assert resp.json()["video_asset"]["frame_id"] == "frame-legacy"


def test_asset_payload_promote_action_requires_video_target(db):
    asset = _seed_image_asset(db, status="approved")
    asset.manual_review_status = "approved"
    asset.audit_status = "approved"
    asset.destination_context_json = {}
    db.commit()

    assert "promote_to_video_asset" not in asset_payload(asset)["allowed_actions"]

    asset.destination_context_json = {"video_run_id": "run-1", "frame_id": "frame-001"}
    db.commit()

    assert "promote_to_video_asset" in asset_payload(asset)["allowed_actions"]


def test_asset_payload_hides_promote_action_for_gate_blocked_approved_asset(db):
    asset = _seed_image_asset(db, status="approved")
    asset.destination_context_json = {"run_id": "run-1", "frame_id": "frame-001"}
    asset.metadata_json = {"review_gate": {"required": False, "status": "blocked"}}
    db.commit()

    assert "promote_to_video_asset" not in asset_payload(asset)["allowed_actions"]


def test_asset_payload_hides_promote_action_when_task_gate_blocks_legacy_asset(db):
    asset = _seed_image_asset(db, status="approved")
    task = db.query(ImageCreationTask).filter_by(id=asset.task_id).one()
    task.request_json = {"review_gate": {"required": True, "manual_required": True, "status": "manual_review_pending"}}
    asset.destination_context_json = {"run_id": "run-1", "frame_id": "frame-001"}
    asset.metadata_json = {}
    asset.manual_review_status = "pending"
    asset.audit_status = "approved"
    db.commit()

    assert "promote_to_video_asset" not in asset_payload(asset)["allowed_actions"]


def test_promote_rejects_when_asset_payload_does_not_allow_promote(db):
    run = _seed_run(db)
    asset = _seed_image_asset(db, status="approved")
    asset.destination_context_json = {}
    db.commit()

    assert "promote_to_video_asset" not in asset_payload(asset)["allowed_actions"]

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={"run_id": run.id, "frame_id": "frame-001", "version": 3, "asset_version": asset.version},
    )

    assert resp.status_code == 409
    assert _error_code(resp) == "IMAGE_ASSET_ACTION_NOT_ALLOWED"


def test_promote_reuses_same_video_asset_and_does_not_duplicate_usage(db):
    run = _seed_run(db)
    asset = _seed_image_asset(db, status="approved")
    payload = {"run_id": run.id, "frame_id": "frame-001", "version": 3}

    first = client.post(f"/api/image-production/assets/{asset.id}/promote-to-video-asset", json=payload)
    second = client.post(f"/api/image-production/assets/{asset.id}/promote-to-video-asset", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["video_asset"]["id"] == second.json()["video_asset"]["id"]
    assert db.query(VideoProductionAsset).count() == 1
    db.refresh(asset)
    assert len(asset.downstream_usage_json) == 1


def test_promote_different_image_to_same_frame_version_returns_conflict(db):
    run = _seed_run(db)
    first_asset = _seed_image_asset(db, status="approved")
    second_asset = _seed_image_asset(db, status="approved")
    second_asset.slot_key = "second-source"
    db.commit()
    payload = {"run_id": run.id, "frame_id": "frame-001", "version": 3}

    first = client.post(f"/api/image-production/assets/{first_asset.id}/promote-to-video-asset", json=payload)
    second = client.post(f"/api/image-production/assets/{second_asset.id}/promote-to-video-asset", json=payload)

    assert first.status_code == 200
    assert second.status_code == 409
    assert _error_code(second) == "VIDEO_ASSET_SLOT_CONFLICT"
    assert db.query(VideoProductionAsset).count() == 1


def test_promote_rejects_existing_slot_without_source_image_identity(db):
    run = _seed_run(db)
    asset = _seed_image_asset(db, status="approved")
    existing = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_review",
        url="https://cdn.test/existing.png",
        version=3,
        metadata_json={},
        status="approved",
    )
    db.add(existing)
    db.commit()

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={"run_id": run.id, "frame_id": "frame-001", "version": 3},
    )

    assert resp.status_code == 409
    assert _error_code(resp) == "VIDEO_ASSET_SLOT_CONFLICT"
    db.refresh(asset)
    assert asset.downstream_usage_json in (None, [])


def test_promote_rejects_asset_from_different_user_scope(db):
    run = _seed_run(db)
    asset = _seed_image_asset(db, status="approved")
    asset.user_id = "other-user-id"
    db.commit()

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={"run_id": run.id, "frame_id": "frame-001", "version": 3},
    )

    assert resp.status_code == 409
    assert _error_code(resp) == "IMAGE_ASSET_SCOPE_CONFLICT"
    assert db.query(VideoProductionAsset).count() == 0


def test_promote_rejects_task_from_different_user_scope(db):
    run = _seed_run(db)
    asset = _seed_image_asset(db, status="approved")
    task = db.query(ImageCreationTask).filter_by(id=asset.task_id).one()
    task.user_id = "other-user-id"
    db.commit()

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={"run_id": run.id, "frame_id": "frame-001", "version": 3},
    )

    assert resp.status_code == 409
    assert _error_code(resp) == "IMAGE_ASSET_SCOPE_CONFLICT"
    assert db.query(VideoProductionAsset).count() == 0


def test_promote_rejects_owned_asset_when_current_user_missing(db):
    run = _seed_run(db)
    asset = _seed_image_asset(db, status="approved")
    asset.user_id = "owner-user-id"
    db.commit()

    try:
        promote_image_asset_to_video_asset(
            db,
            asset.id,
            {"run_id": run.id, "frame_id": "frame-001", "version": 3},
        )
        raise AssertionError("promote should reject missing current user")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
        assert exc.detail["error_code"] == "IMAGE_ASSET_SCOPE_CONFLICT"
    assert db.query(VideoProductionAsset).count() == 0


def test_promote_rejects_payload_episode_that_does_not_match_run(db):
    run = _seed_run(db)
    _, other_episode = _seed_series_episode(db, "Other")
    asset = _seed_image_asset(db, status="approved")

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={
            "run_id": run.id,
            "episode_id": other_episode.id,
            "frame_id": "frame-001",
            "version": 3,
        },
    )

    assert resp.status_code == 409
    assert _error_code(resp) == "IMAGE_ASSET_SCOPE_CONFLICT"
    assert db.query(VideoProductionAsset).count() == 0


def test_promote_rejects_asset_from_different_series_or_episode(db):
    run = _seed_run(db)
    other_series, other_episode = _seed_series_episode(db, "Cross Scope")
    asset = _seed_image_asset(db, status="approved")
    asset.series_id = other_series.id
    asset.episode_id = other_episode.id
    db.commit()

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={"run_id": run.id, "frame_id": "frame-001", "version": 3},
    )

    assert resp.status_code == 409
    assert _error_code(resp) == "IMAGE_ASSET_SCOPE_CONFLICT"
    assert db.query(VideoProductionAsset).count() == 0


def test_promote_rejects_task_from_different_series_or_episode(db):
    run = _seed_run(db)
    other_series, other_episode = _seed_series_episode(db, "Task Cross Scope")
    asset = _seed_image_asset(db, status="approved")
    task = db.query(ImageCreationTask).filter_by(id=asset.task_id).one()
    task.series_id = other_series.id
    task.episode_id = other_episode.id
    db.commit()

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={"run_id": run.id, "frame_id": "frame-001", "version": 3},
    )

    assert resp.status_code == 409
    assert _error_code(resp) == "IMAGE_ASSET_SCOPE_CONFLICT"
    assert db.query(VideoProductionAsset).count() == 0


def test_promote_missing_video_run_returns_not_found(db):
    asset = _seed_image_asset(db, status="approved")

    resp = client.post(
        f"/api/image-production/assets/{asset.id}/promote-to-video-asset",
        json={"run_id": "missing-run", "frame_id": "frame-001", "version": 1},
    )

    assert resp.status_code == 404
    assert _error_code(resp) == "VIDEO_RUN_NOT_FOUND"


def test_promote_image_asset_requires_admin_role(db):
    app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "operator")
    try:
        resp = client.post(
            "/api/image-production/assets/asset-1/promote-to-video-asset",
            json={"run_id": "run-1", "frame_id": "frame-001", "version": 1},
        )
    finally:
        app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "admin")

    assert resp.status_code == 403
