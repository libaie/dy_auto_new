from fastapi.testclient import TestClient

from app.db.models import (
    Episode,
    ProductionEpisode,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)
from app.main import app
from app.domains.video_production.review_asset_edit_service import ReviewAssetEditError


client = TestClient(app)


def _episode(db):
    series = Series(title="Review API", logline="Test", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "Prompt", "duration": 5}]},
    )
    db.add(episode)
    db.commit()
    return series, episode


def _review_run_with_image_asset(db):
    series = Series(title="Review Edit API", logline="Test", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": []},
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_review_pending",
        current_stage="image_review",
        storyboard_json={
            "frames": [{
                "frame_id": "frame-001",
                "reference_urls": ["https://cdn.test/ref.png"],
                "character_ids": ["char-1"],
                "scene_id": "scene-1",
                "continuity_notes": "Keep jacket clean",
                "image_prompt": "Prompt",
            }],
        },
    )
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/old.png",
        version=1,
        status="review_pending",
        is_latest=True,
        copy_status="persisted",
        checksum="abc",
        storage_path="assets/old.png",
    )
    db.add(asset)
    db.commit()
    return run, asset


def test_create_video_production_run(db):
    series, episode = _episode(db)

    resp = client.post("/api/video-production/runs", json={
        "series_id": series.id,
        "episode_id": episode.id,
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["run"]["episode_id"] == episode.id
    assert body["run"]["current_stage"] == "storyboard_ready"


def test_regenerate_creates_new_version(db):
    from app.domains.video_production.video_production_service import create_run_from_episode, mark_image_stage_assets

    series, episode = _episode(db)
    run = create_run_from_episode(db, series.id, episode.id)
    assets = mark_image_stage_assets(db, run, [{
        "frame_id": "frame-001",
        "asset_type": "image",
        "url": "https://cdn.test/v1.png",
        "local_path": "output/v1.png",
        "metadata": {},
    }], pixelle_task_id="stage-1")

    resp = client.post(f"/api/video-production/assets/{assets[0].id}/regenerate", json={
        "url": "https://cdn.test/v2.png",
        "local_path": "output/v2.png",
        "storage_path": "output/v2.png",
        "checksum": "sha256-v2",
        "copy_status": "persisted",
        "metadata": {},
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["asset"]["version"] == 2
    assert body["asset"]["status"] == "review_pending"


def test_regenerate_without_persistence_fields_returns_storage_failed_asset(db):
    from app.domains.video_production.video_production_service import create_run_from_episode, mark_image_stage_assets

    series, episode = _episode(db)
    run = create_run_from_episode(db, series.id, episode.id)
    assets = mark_image_stage_assets(db, run, [{
        "frame_id": "frame-001",
        "asset_type": "image",
        "url": "https://cdn.test/v1.png",
        "local_path": "output/v1.png",
        "metadata": {},
    }], pixelle_task_id="stage-1")

    resp = client.post(f"/api/video-production/assets/{assets[0].id}/regenerate", json={
        "url": "https://cdn.test/v2.png",
        "metadata": {},
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["asset"]["version"] == 2
    assert body["asset"]["status"] == "storage_failed"
    assert body["asset"]["copy_status"] == "storage_failed"


def test_review_items_defaults_to_actionable_statuses(db):
    from app.domains.video_production.video_production_service import create_run_from_episode

    series, episode = _episode(db)
    run = create_run_from_episode(db, series.id, episode.id)
    for index, status in enumerate(["review_pending", "failed", "regenerating", "rejected", "approved"], start=1):
        db.add(VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id=f"frame-{index:03d}",
            asset_type="video_segment",
            stage="video_rendering",
            url=f"https://cdn.test/{status}.mp4",
            version=1,
            status=status,
        ))
    db.commit()

    resp = client.get("/api/video-production/review-items")

    assert resp.status_code == 200
    statuses = {item["status"] for item in resp.json()["items"]}
    assert statuses == {"review_pending", "failed", "regenerating", "rejected"}


def test_review_items_keeps_single_status_filter_compatible(db):
    from app.domains.video_production.video_production_service import create_run_from_episode

    series, episode = _episode(db)
    run = create_run_from_episode(db, series.id, episode.id)
    for status in ["review_pending", "failed"]:
        db.add(VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id=status,
            asset_type="video_segment",
            stage="video_rendering",
            url=f"https://cdn.test/{status}.mp4",
            version=1,
            status=status,
        ))
    db.commit()

    resp = client.get("/api/video-production/review-items", params={"status": "failed"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "failed"


def test_review_items_supports_multiple_statuses(db):
    from app.domains.video_production.video_production_service import create_run_from_episode

    series, episode = _episode(db)
    run = create_run_from_episode(db, series.id, episode.id)
    for status in ["review_pending", "failed", "regenerating"]:
        db.add(VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id=status,
            asset_type="video_segment",
            stage="video_rendering",
            url=f"https://cdn.test/{status}.mp4",
            version=1,
            status=status,
        ))
    db.commit()

    resp = client.get("/api/video-production/review-items?statuses=failed&statuses=regenerating")

    assert resp.status_code == 200
    statuses = {item["status"] for item in resp.json()["items"]}
    assert statuses == {"failed", "regenerating"}


def test_review_items_exposes_production_segment_id_for_real_short_retry(db):
    series, episode = _episode(db)
    plan = ProductionPlan(series_id=series.id, status="running")
    db.add(plan)
    db.flush()
    production_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=1)
    db.add(production_episode)
    db.flush()
    scene = ProductionScene(episode_plan_id=production_episode.id, scene_id="scene-1", order_index=1)
    db.add(scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=scene.id, shot_id="shot-1", order_index=1)
    db.add(shot)
    db.flush()
    segment = ProductionSegment(shot_plan_id=shot.id, segment_id="seg-001", order_index=1, version=1)
    db.add(segment)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_review_pending",
        current_stage="image_review",
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        run_type="real_short_e2e",
    )
    db.add(run)
    db.flush()
    db.add(VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id=segment.id,
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/image.png",
        version=1,
        status="rejected",
        is_latest=True,
        production_segment_id=segment.id,
    ))
    db.commit()

    resp = client.get("/api/video-production/review-items", params={"run_id": run.id})

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["production_segment_id"] == segment.id


def test_review_items_excludes_superseded_asset_versions(db):
    from app.domains.video_production.video_production_service import create_run_from_episode

    series, episode = _episode(db)
    run = create_run_from_episode(db, series.id, episode.id)
    db.add_all([
        VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id="frame-001",
            asset_type="image",
            stage="image_generation",
            url="https://cdn.test/v1.png",
            version=1,
            status="review_pending",
            is_latest=False,
        ),
        VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id="frame-001",
            asset_type="image",
            stage="image_generation",
            url="https://cdn.test/v2.png",
            version=2,
            status="review_pending",
            is_latest=True,
        ),
    ])
    db.commit()

    resp = client.get(f"/api/video-production/review-items?run_id={run.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert [item["version"] for item in body["items"]] == [2]


def test_review_items_exposes_approval_permission_from_persistence_state(db):
    from app.domains.video_production.video_production_service import create_run_from_episode

    series, episode = _episode(db)
    run = create_run_from_episode(db, series.id, episode.id)
    db.add_all([
        VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id="ready",
            asset_type="image",
            stage="image_generation",
            url="https://cdn.test/ready.png",
            version=1,
            status="review_pending",
            copy_status="persisted",
            checksum="sha256:ready",
            storage_path="video-production/ready.png",
        ),
        VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id="registered",
            asset_type="image",
            stage="image_generation",
            url="https://cdn.test/registered.png",
            version=1,
            status="review_pending",
            copy_status="registered",
            checksum=None,
            storage_path=None,
        ),
        VideoProductionAsset(
            run_id=run.id,
            episode_id=episode.id,
            frame_id="failed-persisted",
            asset_type="image",
            stage="image_generation",
            url="https://cdn.test/failed.png",
            version=1,
            status="failed",
            copy_status="persisted",
            checksum="sha256:failed",
            storage_path="video-production/failed.png",
        ),
    ])
    db.commit()

    resp = client.get(f"/api/video-production/review-items?run_id={run.id}")

    assert resp.status_code == 200
    by_frame = {item["frame_id"]: item for item in resp.json()["items"]}
    assert by_frame["ready"]["permission"]["can_approve"] is True
    assert by_frame["registered"]["permission"]["can_approve"] is False
    assert by_frame["failed-persisted"]["permission"]["can_approve"] is False


def test_persist_retry_runs_ai_audit_before_returning_reviewable_asset(db, monkeypatch):
    from app.domains.video_production.video_production_service import create_run_from_episode

    series, episode = _episode(db)
    run = create_run_from_episode(db, series.id, episode.id)
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/retry.png",
        source_url="https://cdn.test/retry.png",
        version=1,
        status="storage_failed",
        copy_status="storage_failed",
    )
    db.add(asset)
    db.commit()
    audited = []

    def fake_persist_provider_asset(db, asset_id, *, output_root, pixelle_output_root=None):
        del output_root, pixelle_output_root
        saved = db.query(VideoProductionAsset).filter_by(id=asset_id).one()
        saved.copy_status = "persisted"
        saved.status = "review_pending"
        saved.storage_path = f"output/video-production/{saved.id}.png"
        saved.checksum = "sha256-retry"
        db.commit()
        db.refresh(saved)
        return saved

    def fake_audit(db, run, assets):
        audited.extend(asset.id for asset in assets)
        for saved in assets:
            db.add(VideoReviewRecord(
                asset_id=saved.id,
                run_id=run.id,
                review_type="ai",
                status="needs_human",
                score=0.0,
            ))
        db.commit()
        return assets

    monkeypatch.setattr("app.domains.video_production.asset_storage_guard.persist_provider_asset", fake_persist_provider_asset)
    monkeypatch.setattr("app.domains.video_production.video_production_service.run_ai_audit_for_assets", fake_audit)

    resp = client.post(f"/api/video-production/assets/{asset.id}/persist-retry")

    assert resp.status_code == 200
    body = resp.json()
    assert body["asset"]["permission"]["can_approve"] is True
    assert audited == [asset.id]
    assert db.query(VideoReviewRecord).filter_by(asset_id=asset.id, review_type="ai").count() == 1


def test_persist_retry_rejects_already_persisted_assets(db):
    from app.domains.video_production.video_production_service import create_run_from_episode

    series, episode = _episode(db)
    run = create_run_from_episode(db, series.id, episode.id)
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/ready.png",
        source_url="https://cdn.test/ready.png",
        version=1,
        status="review_pending",
        copy_status="persisted",
        checksum="sha256-ready",
        storage_path="output/video-production/ready.png",
    )
    db.add(asset)
    db.commit()

    resp = client.post(f"/api/video-production/assets/{asset.id}/persist-retry")

    assert resp.status_code == 409


def test_image_edit_pending_response_has_sync_payload(db, monkeypatch):
    _, asset = _review_run_with_image_asset(db)

    async def fake_edit(db, asset_id, instruction, expected_version=None):
        raise ReviewAssetEditError(
            "IMAGE_EDIT_TASK_QUEUED",
            "Image edit task is queued.",
            {"image_task_id": "task-1", "status": "queued"},
        )

    monkeypatch.setattr("app.domains.video_production.video_production_router.edit_image_asset", fake_edit)

    resp = client.post(f"/api/video-production/assets/{asset.id}/image-edit", json={
        "instruction": "保持角色脸型一致",
        "expected_version": asset.version,
    })

    assert resp.status_code == 202
    data = resp.json()
    assert data["ok"] is False
    assert data["status"] == "pending"
    assert data["code"] == "IMAGE_EDIT_TASK_QUEUED"
    assert data["message"] == "改图任务已提交，等待生成结果同步。"
    assert data["image_creation_task_id"] == "task-1"
    assert data["warnings"][0]["code"] == "IMAGE_EDIT_TASK_QUEUED"
    assert data["missing_requirements"] == []


def test_void_asset_rejects_stale_expected_version(db):
    _, asset = _review_run_with_image_asset(db)

    resp = client.post(f"/api/video-production/assets/{asset.id}/void", json={
        "comment": "old version",
        "expected_version": asset.version - 1,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "STALE_ASSET_VERSION"


def test_review_item_payload_includes_reference_evidence(db):
    run, _ = _review_run_with_image_asset(db)

    resp = client.get(f"/api/video-production/review-items?run_id={run.id}")

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["reference_evidence"] == {
        "reference_urls": ["https://cdn.test/ref.png"],
        "character_ids": ["char-1"],
        "scene_id": "scene-1",
        "continuity_notes": "Keep jacket clean",
        "image_prompt": "Prompt",
        "character_reference_urls": [],
        "style_reference_urls": [],
        "missing": [],
    }


def test_review_item_payload_has_empty_reference_evidence_for_missing_frame(db):
    run, asset = _review_run_with_image_asset(db)
    asset.frame_id = "missing-frame"
    db.commit()

    resp = client.get(f"/api/video-production/review-items?run_id={run.id}")

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["storyboard_frame"] == {}
    assert item["reference_evidence"] == {
        "reference_urls": [],
        "character_ids": [],
        "scene_id": None,
        "continuity_notes": None,
        "image_prompt": None,
        "character_reference_urls": [],
        "style_reference_urls": [],
        "missing": [],
    }
