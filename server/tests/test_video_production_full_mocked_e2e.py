from fastapi.testclient import TestClient
from app.db_models import Episode, GeneratedVideo, ProductionAuditEvent, Series, VideoProductionAsset, VideoProductionRun
from app.main import app

client = TestClient(app)


async def _agency_pass(*args, **kwargs):
    return {"stage_status": "passed", "invocation_ids": ["agency-ok"], "invocations": []}


def test_storyboard_to_final_video_mocked_e2e(db, monkeypatch):
    series = Series(title="Full E2E", logline="Test", genre="drama", target_duration=30)
    db.add(series); db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot",
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "Prompt", "video_prompt": "Move", "narration": "Hello", "duration": 5}]})
    db.add(episode); db.commit()

    stage = {"current": None}

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        stage["current"] = "image"; return {"ok": True, "stage_task_id": "image-task"}

    async def fake_submit_video_batch(db, run_id, frames, model_config, template_config=None):
        stage["current"] = "video"; return {"ok": True, "stage_task_id": "video-task"}

    async def fake_submit_compose(db, run_id, segments, edit_manifest, model_config=None):
        stage["current"] = "compose"; return {"ok": True, "stage_task_id": "compose-task"}

    async def fake_get_stage_task(db, stage_task_id):
        if stage_task_id == "image-task":
            return {"ok": True, "status": "completed", "assets": [{
                "frame_id": "frame-001",
                "asset_type": "image",
                "url": "image.png",
                "storage_path": "output/image.png",
                "checksum": "checksum-image",
                "copy_status": "persisted",
                "metadata": {"duration": 5},
            }]}
        if stage_task_id == "video-task":
            return {"ok": True, "status": "completed", "assets": [{
                "frame_id": "frame-001",
                "asset_type": "video_segment",
                "url": "segment.mp4",
                "storage_path": "output/segment.mp4",
                "checksum": "checksum-segment",
                "copy_status": "persisted",
                "metadata": {"duration": 5},
            }]}
        return {"ok": True, "status": "completed", "assets": [{
            "frame_id": "final",
            "asset_type": "final_video",
            "url": "final.mp4",
            "local_path": "output/final.mp4",
            "storage_path": "output/final.mp4",
            "checksum": "checksum-final",
            "copy_status": "persisted",
            "metadata": {"duration": 5},
        }]}

    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "api_key": "x", "scene_key": scene})
    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", _agency_pass)
    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", fake_submit_video_batch)
    monkeypatch.setattr("app.services.video_production_service.submit_compose", fake_submit_compose)
    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.routers.audit._do_audit", lambda model, url, text: {"score": 0.99, "pass_fail": True, "issues": []})

    created = client.post("/api/video-production/runs", json={"series_id": series.id, "episode_id": episode.id}).json()
    run_id = created["run"]["id"]

    assert client.post(f"/api/video-production/runs/{run_id}/start-images").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/sync-image-results").status_code == 200
    image_asset = db.query(VideoProductionAsset).filter_by(run_id=run_id, asset_type="image").one()
    assert image_asset.status == "review_pending"
    assert client.post(f"/api/video-production/assets/{image_asset.id}/review", json={"action": "approve"}).status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/start-videos").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/sync-video-results").status_code == 200
    video_asset = db.query(VideoProductionAsset).filter_by(run_id=run_id, asset_type="video_segment").one()
    assert video_asset.status == "review_pending"
    assert client.post(f"/api/video-production/assets/{video_asset.id}/review", json={"action": "approve"}).status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/compose").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/sync-compose-results").status_code == 200

    final = client.get(f"/api/video-production/runs/{run_id}").json()
    assert final["run"]["status"] == "final_review_pending"
    db.refresh(episode)
    assert not episode.video_url
    assert episode.status != "done"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run_id).count() == 0

    final_asset = db.query(VideoProductionAsset).filter_by(run_id=run_id, asset_type="final_video").one()
    assert final_asset.status == "review_pending"
    assert client.post(f"/api/video-production/assets/{final_asset.id}/review", json={"action": "approve"}).status_code == 200

    db.refresh(episode)
    assert episode.video_url == "output/final.mp4"
    assert episode.status == "done"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run_id).count() == 1


def test_linked_start_to_final_video_mocked_e2e(db, monkeypatch):
    series = Series(
        title="Linked Full E2E",
        logline="Test",
        genre="drama",
        target_duration=12,
        story_bible_json={
            "style_lock": {
                "locked": True,
                "version": 1,
                "visual_style": {"reference_urls": ["https://cdn.test/style.png"]},
            }
        },
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={
            "frames": [{
                "frame_id": "frame-001",
                "scene_id": "scene-1",
                "character_ids": ["hero"],
                "image_prompt": "Hero enters a neon clinic.",
                "video_prompt": "Slow push toward the hero.",
                "narration": "The clinic lights flicker.",
                "duration": 6,
                "reference_urls": ["https://cdn.test/hero.png"],
            }]
        },
    )
    db.add(episode)
    db.commit()

    submitted = {"image": [], "video": [], "compose": []}

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        submitted["image"] = frames
        return {"ok": True, "stage_task_id": "image-task"}

    async def fake_submit_video_batch(db, run_id, frames, model_config, template_config=None):
        submitted["video"] = frames
        return {"ok": True, "stage_task_id": "video-task"}

    async def fake_submit_compose(db, run_id, segments, edit_manifest, model_config=None):
        submitted["compose"] = segments
        return {"ok": True, "stage_task_id": "compose-task"}

    async def fake_get_stage_task(db, stage_task_id):
        if stage_task_id == "image-task":
            segment_id = submitted["image"][0]["production_segment_id"]
            return {
                "ok": True,
                "status": "completed",
                "assets": [{
                    "frame_id": segment_id,
                    "asset_type": "image",
                    "url": "image.png",
                    "storage_path": f"output/{segment_id}.png",
                    "checksum": f"checksum-image-{segment_id}",
                    "copy_status": "persisted",
                    "metadata": {"duration": 6},
                }],
            }
        if stage_task_id == "video-task":
            segment_id = submitted["video"][0]["production_segment_id"]
            return {
                "ok": True,
                "status": "completed",
                "assets": [{
                    "frame_id": segment_id,
                    "asset_type": "video_segment",
                    "url": "segment.mp4",
                    "storage_path": f"output/{segment_id}.mp4",
                    "checksum": f"checksum-video-{segment_id}",
                    "copy_status": "persisted",
                    "metadata": {"duration": 6},
                }],
            }
        return {
            "ok": True,
            "status": "completed",
            "assets": [{
                "frame_id": "final",
                "asset_type": "final_video",
                "url": "final-linked.mp4",
                "local_path": "output/final-linked.mp4",
                "storage_path": "output/final-linked.mp4",
                "checksum": "checksum-final-linked",
                "copy_status": "persisted",
                "metadata": {"duration": 6},
            }],
        }

    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "api_key": "x", "scene_key": scene})
    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", _agency_pass)
    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", fake_submit_video_batch)
    monkeypatch.setattr("app.services.video_production_service.submit_compose", fake_submit_compose)
    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.routers.audit._do_audit", lambda model, url, text: {"score": 0.99, "pass_fail": True, "issues": []})

    created = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 12,
        # This scenario validates explicit human approval at each gate.
        "autostart_images": False,
    })
    assert created.status_code == 200
    run_id = created.json()["run"]["id"]

    assert client.post(f"/api/video-production/runs/{run_id}/start-images").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/sync-image-results").status_code == 200
    image_ids = [asset.id for asset in db.query(VideoProductionAsset).filter_by(run_id=run_id, asset_type="image").all()]
    for image_id in image_ids:
        assert client.post(f"/api/video-production/assets/{image_id}/review", json={"action": "approve"}).status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/start-videos").status_code == 200
    assert submitted["video"][0]["production_segment_id"] == submitted["image"][0]["production_segment_id"]

    assert client.post(f"/api/video-production/runs/{run_id}/sync-video-results").status_code == 200
    video_ids = [asset.id for asset in db.query(VideoProductionAsset).filter_by(run_id=run_id, asset_type="video_segment").all()]
    for video_id in video_ids:
        assert client.post(f"/api/video-production/assets/{video_id}/review", json={"action": "approve"}).status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/compose").status_code == 200
    assert submitted["compose"][0]["frame_id"] == submitted["video"][0]["production_segment_id"]

    assert client.post(f"/api/video-production/runs/{run_id}/sync-compose-results").status_code == 200

    db.refresh(episode)
    run = db.query(VideoProductionRun).filter_by(id=run_id).one()
    final_asset = db.query(VideoProductionAsset).filter_by(run_id=run_id, asset_type="final_video").one()
    assert run.status == "final_review_pending"
    assert final_asset.status == "review_pending"
    assert not episode.video_url
    assert episode.status != "done"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run_id).count() == 0

    assert client.post(f"/api/video-production/assets/{final_asset.id}/review", json={"action": "approve"}).status_code == 200

    db.refresh(episode)
    db.refresh(run)
    assert episode.video_url == "output/final-linked.mp4"
    assert episode.status == "done"
    assert run.status == "completed"
    assert run.production_link_status == "linked"
    assert db.query(VideoProductionAsset).filter_by(run_id=run_id, is_latest=True).count() >= 1
    assert db.query(ProductionAuditEvent).filter_by(run_id=run_id).count() >= 5
