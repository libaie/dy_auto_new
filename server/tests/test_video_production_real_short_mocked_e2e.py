from fastapi.testclient import TestClient

from app.db.models import Character, Episode, GeneratedVideo, Scene, VideoProductionAsset, VideoProductionRun
from app.main import app
from app.domains.video_production.video_production_state import production_segment_frame_ids
from app.domains.video_production.video_production_run_types import REAL_SHORT_E2E
from app.domains.model_configuration.runtime_model_config import RuntimeModelConfigError

client = TestClient(app)


async def _agency_pass(*args, **kwargs):
    return {"stage_status": "passed", "invocation_ids": ["agency-ok"], "invocations": []}


async def _fake_character_references(db, character_id, slot="all"):
    character = db.query(Character).filter_by(id=character_id).one()
    character.avatar_front_url = "/static/image-creation/character-front.png"
    character.avatar_side_url = "/static/image-creation/character-side.png"
    db.commit()
    return {"ok": True, "generated": [{"slot": "avatar_front_url", "url": character.avatar_front_url}]}


async def _fake_scene_references(db, scene_id, slot="all"):
    scene = db.query(Scene).filter_by(id=scene_id).one()
    scene.reference_wideshot_url = "/static/image-creation/scene-wide.png"
    scene.reference_midshot_url = "/static/image-creation/scene-mid.png"
    db.commit()
    return {"ok": True, "generated": [{"slot": "reference_wideshot_url", "url": scene.reference_wideshot_url}]}


def test_real_short_e2e_requires_human_image_video_and_final_gates(db, monkeypatch):
    submitted = {"image": {}, "video": {}, "compose": {}}

    class FakeAgencyOrchestrator:
        async def run_style_lock_review(self, *args, **kwargs):
            return {"stage_status": "passed", "invocation_ids": ["style-ok"], "invocations": []}

        async def run_storyboard_review(self, *args, **kwargs):
            return {"stage_status": "passed", "invocation_ids": ["storyboard-ok"], "invocations": []}

    def fake_one_sentence_config(db, scene_key):
        return {"provider": "mock", "api_key": "x", "model_name": scene_key}

    def fake_stage_config(db, scene_key):
        return {
            "provider": "mock",
            "api_key": "x",
            "model_name": scene_key,
            "capability": {
                "real_paid_allowed": True,
                "supports_external_task_id": True,
                "supports_task_query": True,
                "returns_asset_url": True,
                "returns_usage": True,
                "estimated_cost": 0.01,
                "supports_text_to_image": scene_key == "image_generation",
                "supports_image_to_video": scene_key == "video_rendering",
                "supports_video_composition": scene_key == "video_composition",
                "max_concurrent_tasks": 10,
            },
        }

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        task_id = f"image-task-{frames[0]['production_segment_id']}"
        submitted["image"][task_id] = frames
        return {"ok": True, "stage_task_id": task_id}

    async def fake_submit_video_batch(db, run_id, frames, model_config, template_config=None):
        task_id = f"video-task-{frames[0]['production_segment_id']}"
        submitted["video"][task_id] = frames
        return {"ok": True, "stage_task_id": task_id}

    async def fake_submit_compose(db, run_id, segments, edit_manifest, model_config=None):
        submitted["compose"]["compose-task"] = segments
        return {"ok": True, "stage_task_id": "compose-task"}

    async def fake_get_stage_task(db, stage_task_id):
        if stage_task_id in submitted["image"]:
            return {
                "ok": True,
                "status": "completed",
                "assets": [
                    {
                        "frame_id": frame["production_segment_id"],
                        "production_segment_id": frame["production_segment_id"],
                        "asset_type": "image",
                        "url": f"https://cdn.test/{frame['production_segment_id']}.png",
                        "source_url": f"https://cdn.test/{frame['production_segment_id']}.png",
                        "storage_path": f"output/{frame['production_segment_id']}.png",
                        "checksum": f"checksum-image-{frame['production_segment_id']}",
                        "copy_status": "persisted",
                        "metadata": {"duration": frame["duration"]},
                    }
                    for frame in submitted["image"][stage_task_id]
                ],
                "usage": {"actual_cost": 0.01, "units": {"images": len(submitted["image"][stage_task_id])}},
            }
        if stage_task_id in submitted["video"]:
            return {
                "ok": True,
                "status": "completed",
                "assets": [
                    {
                        "frame_id": frame["production_segment_id"],
                        "production_segment_id": frame["production_segment_id"],
                        "asset_type": "video_segment",
                        "url": f"https://cdn.test/{frame['production_segment_id']}.mp4",
                        "source_url": f"https://cdn.test/{frame['production_segment_id']}.mp4",
                        "storage_path": f"output/{frame['production_segment_id']}.mp4",
                        "checksum": f"checksum-video-{frame['production_segment_id']}",
                        "copy_status": "persisted",
                        "metadata": {"duration": frame["duration"]},
                    }
                    for frame in submitted["video"][stage_task_id]
                ],
                "usage": {"actual_cost": 0.02, "units": {"videos": len(submitted["video"][stage_task_id])}},
            }
        return {
            "ok": True,
            "status": "completed",
            "assets": [{
                "frame_id": "final",
                "asset_type": "final_video",
                "url": "https://cdn.test/final-real-short.mp4",
                "source_url": "https://cdn.test/final-real-short.mp4",
                "local_path": "output/final-real-short.mp4",
                "storage_path": "output/final-real-short.mp4",
                "checksum": "checksum-final-real-short",
                "copy_status": "persisted",
                "metadata": {"duration": 60},
            }],
            "usage": {"actual_cost": 0.03, "units": {"videos": 1}},
        }

    monkeypatch.setattr("app.domains.video_production.one_sentence_video_service.AgencyOrchestrator", FakeAgencyOrchestrator)
    monkeypatch.setattr(
        "app.domains.creative_library.reference_asset_service.generate_character_reference_images",
        _fake_character_references,
    )
    monkeypatch.setattr(
        "app.domains.creative_library.reference_asset_service.generate_scene_reference_images",
        _fake_scene_references,
    )
    monkeypatch.setattr("app.domains.video_production.one_sentence_video_service.resolve_runtime_model_config", fake_one_sentence_config)
    monkeypatch.setattr("app.domains.video_production.video_production_service.resolve_runtime_model_config", fake_stage_config)
    monkeypatch.setattr("app.domains.video_production.production_worker_service.resolve_runtime_model_config", fake_stage_config)
    monkeypatch.setattr("app.domains.video_production.video_production_service._guard_provider_stage", _agency_pass)
    monkeypatch.setattr("app.domains.video_production.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.domains.video_production.video_production_service.submit_video_batch", fake_submit_video_batch)
    monkeypatch.setattr("app.domains.video_production.video_production_service.submit_compose", fake_submit_compose)
    monkeypatch.setattr("app.domains.video_production.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.domains.video_production.production_worker_service.run_ai_audit_for_assets", lambda db, run, assets: assets)
    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")
    monkeypatch.setattr("app.domains.quality_audit.audit_router._do_audit", lambda model, url, text: {"score": 0.2, "pass_fail": False, "issues": []})

    create_resp = client.post(
        "/api/video-production/one-sentence",
        json={
            "prompt": "A courier crosses a rainy neon city to deliver one impossible message.",
            "title": "Rain Courier",
            "run_type": REAL_SHORT_E2E,
            "target_duration_seconds": 60,
            "budget_limit": 1.0,
            "autostart_images": True,
        },
    )

    assert create_resp.status_code == 200
    body = create_resp.json()
    run_id = body["run"]["id"]
    episode_id = body["episode"]["id"]
    assert body["run"]["run_type"] == REAL_SHORT_E2E
    assert body["run"]["status"] == "image_batch_running"

    image_worker = client.post(
        f"/api/video-production/runs/{run_id}/worker-step",
        json={"lease_id": "worker-images", "batch_size": 100},
    )
    assert image_worker.status_code == 200
    assert image_worker.json()["processed"] > 0
    assert image_worker.json()["remaining"] == 0, image_worker.json()
    blocked_video = client.post(f"/api/video-production/runs/{run_id}/start-videos")
    assert 400 <= blocked_video.status_code < 500
    assert "images are approved" in blocked_video.text

    image_ids = [
        asset.id
        for asset in db.query(VideoProductionAsset).filter_by(
            run_id=run_id,
            asset_type="image",
            status="review_pending",
        ).all()
    ]
    assert image_ids
    for asset_id in image_ids:
        assert client.post(f"/api/video-production/assets/{asset_id}/review", json={"action": "approve"}).status_code == 200
    db.expire_all()
    approved_images = db.query(VideoProductionAsset).filter_by(run_id=run_id, asset_type="image", status="approved").count()
    assert approved_images == len(image_ids)
    run = db.query(VideoProductionRun).filter_by(id=run_id).one()
    assert approved_images == len(production_segment_frame_ids(db, run))

    start_videos = client.post(f"/api/video-production/runs/{run_id}/start-videos")
    assert start_videos.status_code == 200, start_videos.text
    video_worker = client.post(
        f"/api/video-production/runs/{run_id}/worker-step",
        json={"lease_id": "worker-videos", "batch_size": 100},
    )
    assert video_worker.status_code == 200
    assert video_worker.json()["processed"] > 0
    blocked_compose = client.post(f"/api/video-production/runs/{run_id}/compose")
    assert 400 <= blocked_compose.status_code < 500
    assert "video segments are approved" in blocked_compose.text

    video_ids = [
        asset.id
        for asset in db.query(VideoProductionAsset).filter_by(
            run_id=run_id,
            asset_type="video_segment",
            status="review_pending",
        ).all()
    ]
    assert video_ids
    for asset_id in video_ids:
        assert client.post(f"/api/video-production/assets/{asset_id}/review", json={"action": "approve"}).status_code == 200

    assert client.post(f"/api/video-production/runs/{run_id}/compose").status_code == 200
    compose_worker = client.post(
        f"/api/video-production/runs/{run_id}/worker-step",
        json={"lease_id": "worker-compose", "batch_size": 1},
    )
    assert compose_worker.status_code == 200
    assert compose_worker.json()["processed"] == 1
    assert compose_worker.json()["items"][0]["ok"] is True

    db.expire_all()
    run = db.query(VideoProductionRun).filter_by(id=run_id).one()
    final_asset = db.query(VideoProductionAsset).filter_by(run_id=run_id, asset_type="final_video").one()
    episode = db.query(Episode).filter_by(id=episode_id).one()
    assert run.status == "final_review_pending"
    assert run.current_stage == "final_review"
    assert final_asset.status == "review_pending"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run_id).count() == 0
    assert episode.status != "done"
    assert not episode.video_url

    assert client.post(
        f"/api/video-production/assets/{final_asset.id}/review",
        json={"action": "approve", "comment": "final approved"},
    ).status_code == 200

    db.refresh(run)
    db.refresh(episode)
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run_id).count() == 1
    assert episode.video_url == "output/final-real-short.mp4"
    assert episode.status == "done"
    assert run.status == "completed"


def test_real_short_e2e_autopilot_stops_for_final_human_review_when_audit_model_missing(db, monkeypatch):
    submitted = {"image": {}, "video": {}, "compose": {}}

    class FakeAgencyOrchestrator:
        async def run_style_lock_review(self, *args, **kwargs):
            return {"stage_status": "passed", "invocation_ids": ["style-ok"], "invocations": []}

        async def run_storyboard_review(self, *args, **kwargs):
            return {"stage_status": "passed", "invocation_ids": ["storyboard-ok"], "invocations": []}

    def fake_one_sentence_config(db, scene_key):
        return {"provider": "mock", "api_key": "x", "model_name": scene_key}

    def fake_stage_config(db, scene_key):
        if scene_key == "quality_audit":
            raise RuntimeModelConfigError("quality_audit not configured")
        return {
            "provider": "mock",
            "api_key": "x",
            "model_name": scene_key,
            "capability": {
                "real_paid_allowed": True,
                "supports_external_task_id": True,
                "supports_task_query": True,
                "returns_asset_url": True,
                "returns_usage": True,
                "estimated_cost": 0.01,
                "supports_text_to_image": scene_key == "image_generation",
                "supports_image_to_video": scene_key == "video_rendering",
                "supports_video_composition": scene_key == "video_composition",
                "max_concurrent_tasks": 10,
            },
        }

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        task_id = f"image-task-{frames[0]['production_segment_id']}"
        submitted["image"][task_id] = frames
        return {"ok": True, "stage_task_id": task_id}

    async def fake_submit_video_batch(db, run_id, frames, model_config, template_config=None):
        task_id = f"video-task-{frames[0]['production_segment_id']}"
        submitted["video"][task_id] = frames
        return {"ok": True, "stage_task_id": task_id}

    async def fake_submit_compose(db, run_id, segments, edit_manifest, model_config=None):
        submitted["compose"]["compose-task"] = segments
        return {"ok": True, "stage_task_id": "compose-task"}

    async def fake_get_stage_task(db, stage_task_id):
        if stage_task_id in submitted["image"]:
            return {
                "ok": True,
                "status": "completed",
                "assets": [
                    {
                        "frame_id": frame["production_segment_id"],
                        "production_segment_id": frame["production_segment_id"],
                        "asset_type": "image",
                        "url": f"https://cdn.test/{frame['production_segment_id']}.png",
                        "source_url": f"https://cdn.test/{frame['production_segment_id']}.png",
                        "storage_path": f"output/{frame['production_segment_id']}.png",
                        "checksum": f"checksum-image-{frame['production_segment_id']}",
                        "copy_status": "persisted",
                        "metadata": {"duration": frame["duration"]},
                    }
                    for frame in submitted["image"][stage_task_id]
                ],
                "usage": {"actual_cost": 0.01, "units": {"images": len(submitted["image"][stage_task_id])}},
            }
        if stage_task_id in submitted["video"]:
            return {
                "ok": True,
                "status": "completed",
                "assets": [
                    {
                        "frame_id": frame["production_segment_id"],
                        "production_segment_id": frame["production_segment_id"],
                        "asset_type": "video_segment",
                        "url": f"https://cdn.test/{frame['production_segment_id']}.mp4",
                        "source_url": f"https://cdn.test/{frame['production_segment_id']}.mp4",
                        "storage_path": f"output/{frame['production_segment_id']}.mp4",
                        "checksum": f"checksum-video-{frame['production_segment_id']}",
                        "copy_status": "persisted",
                        "metadata": {"duration": frame["duration"]},
                    }
                    for frame in submitted["video"][stage_task_id]
                ],
                "usage": {"actual_cost": 0.02, "units": {"videos": len(submitted["video"][stage_task_id])}},
            }
        return {
            "ok": True,
            "status": "completed",
            "assets": [{
                "frame_id": "final",
                "asset_type": "final_video",
                "url": "https://cdn.test/final-autopilot.mp4",
                "source_url": "https://cdn.test/final-autopilot.mp4",
                "local_path": "output/final-autopilot.mp4",
                "storage_path": "output/final-autopilot.mp4",
                "checksum": "checksum-final-autopilot",
                "copy_status": "persisted",
                "metadata": {"duration": 60},
            }],
            "usage": {"actual_cost": 0.03, "units": {"videos": 1}},
        }

    monkeypatch.setattr("app.domains.video_production.one_sentence_video_service.AgencyOrchestrator", FakeAgencyOrchestrator)
    monkeypatch.setattr(
        "app.domains.creative_library.reference_asset_service.generate_character_reference_images",
        _fake_character_references,
    )
    monkeypatch.setattr(
        "app.domains.creative_library.reference_asset_service.generate_scene_reference_images",
        _fake_scene_references,
    )
    monkeypatch.setattr("app.domains.video_production.one_sentence_video_service.resolve_runtime_model_config", fake_one_sentence_config)
    monkeypatch.setattr("app.domains.video_production.video_production_service.resolve_runtime_model_config", fake_stage_config)
    monkeypatch.setattr("app.domains.video_production.production_worker_service.resolve_runtime_model_config", fake_stage_config)
    monkeypatch.setattr("app.domains.video_production.video_production_service._guard_provider_stage", _agency_pass)
    monkeypatch.setattr("app.domains.video_production.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.domains.video_production.video_production_service.submit_video_batch", fake_submit_video_batch)
    monkeypatch.setattr("app.domains.video_production.video_production_service.submit_compose", fake_submit_compose)
    monkeypatch.setattr("app.domains.video_production.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setenv("DY_AUTO_PROVIDER_SUBMIT_WORKER_COUNT", "1")

    create_resp = client.post(
        "/api/video-production/one-sentence",
        json={
            "prompt": "A courier crosses a rainy neon city to deliver one impossible message.",
            "title": "Rain Courier Autopilot",
            "run_type": REAL_SHORT_E2E,
            "target_duration_seconds": 60,
            "budget_limit": 1.0,
            "autostart_images": True,
        },
    )

    assert create_resp.status_code == 200
    body = create_resp.json()
    run_id = body["run"]["id"]
    episode_id = body["episode"]["id"]
    assert body["run"]["model_trace_json"]["autopilot"] == {"enabled": True, "source": "one_sentence"}

    image_worker = client.post(
        f"/api/video-production/runs/{run_id}/worker-step",
        json={"lease_id": "worker-images", "batch_size": 100},
    )
    assert image_worker.status_code == 200
    db.expire_all()
    run = db.query(VideoProductionRun).filter_by(id=run_id).one()
    assert run.status == "image_approved"
    assert db.query(VideoProductionAsset).filter_by(run_id=run_id, asset_type="image", status="approved").count() == len(production_segment_frame_ids(db, run))

    start_videos = client.post(f"/api/video-production/runs/{run_id}/start-videos")
    assert start_videos.status_code == 200, start_videos.text
    video_worker = client.post(
        f"/api/video-production/runs/{run_id}/worker-step",
        json={"lease_id": "worker-videos", "batch_size": 100},
    )
    assert video_worker.status_code == 200
    db.expire_all()
    run = db.query(VideoProductionRun).filter_by(id=run_id).one()
    assert run.status == "video_segments_approved"
    assert db.query(VideoProductionAsset).filter_by(run_id=run_id, asset_type="video_segment", status="approved").count() == len(production_segment_frame_ids(db, run))

    assert client.post(f"/api/video-production/runs/{run_id}/compose").status_code == 200
    compose_worker = client.post(
        f"/api/video-production/runs/{run_id}/worker-step",
        json={"lease_id": "worker-compose", "batch_size": 1},
    )
    assert compose_worker.status_code == 200
    assert compose_worker.json()["items"][0]["ok"] is True

    db.expire_all()
    run = db.query(VideoProductionRun).filter_by(id=run_id).one()
    episode = db.query(Episode).filter_by(id=episode_id).one()
    final_asset = db.query(VideoProductionAsset).filter_by(run_id=run_id, asset_type="final_video").one()
    assert final_asset.status == "review_pending"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run_id).count() == 0
    assert episode.video_url is None
    assert episode.status != "done"
    assert run.status == "final_review_pending"

    approve_final = client.post(
        f"/api/video-production/assets/{final_asset.id}/review",
        json={"action": "approve", "comment": "final human approval"},
    )
    assert approve_final.status_code == 200

    db.expire_all()
    run = db.query(VideoProductionRun).filter_by(id=run_id).one()
    episode = db.query(Episode).filter_by(id=episode_id).one()
    final_asset = db.query(VideoProductionAsset).filter_by(id=final_asset.id).one()
    assert final_asset.status == "approved"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run_id).count() == 1
    assert episode.video_url == "output/final-autopilot.mp4"
    assert episode.status == "done"
    assert run.status == "completed"
