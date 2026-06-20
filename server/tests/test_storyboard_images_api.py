from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import bj_now
from app.db.models import Episode, ImageCreationAsset, ImageCreationTask, Series, VideoProductionAsset, VideoProductionRun
from app.main import app


client = TestClient(app)


def _series_episode(db):
    series = Series(title="Storyboard Images API", logline="API closure", status="active", target_duration=4)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Episode 1",
        duration_seconds=4,
        storyboard_json={
            "frames": [
                {
                    "frame_id": "shot-001",
                    "time_range": "0-2秒",
                    "duration": 2,
                    "image_prompt": "时间段: 0-2秒\n主体/角色: 老李\n画面动作: 老李抬头。",
                    "reference_urls": ["/static/image-creation/reference.png"],
                },
                {
                    "frame_id": "shot-002",
                    "time_range": "2-4秒",
                    "duration": 2,
                    "image_prompt": "时间段: 2-4秒\n主体/角色: 老李\n画面动作: 老李追问。",
                    "reference_urls": ["/static/image-creation/reference.png"],
                },
            ]
        },
    )
    db.add(episode)
    db.commit()
    return series, episode


def _task_from_payload(payload: dict) -> ImageCreationTask:
    return ImageCreationTask(
        id=f"task-{payload['destination_context']['frame_id']}",
        mode=payload["mode"],
        output_mode="single",
        capability_key="text_to_image",
        status="running",
        series_id=payload["series_id"],
        episode_id=payload["episode_id"],
        prompt=payload["prompt"],
        reference_images_json=payload.get("reference_images") or [],
        destination_role=payload["destination_role"],
        destination_context_json=payload["destination_context"],
        count=payload.get("count") or 1,
        target_count=payload.get("count") or 1,
        request_json={},
        estimated_cost_json={},
        created_at=bj_now(),
    )


@pytest.fixture
def fake_storyboard_image_creation(monkeypatch):
    calls = []

    async def fake_create_image_task(db_session, payload):
        calls.append(payload)
        return _task_from_payload(payload)

    monkeypatch.setattr("app.domains.storyboard_images.storyboard_image_service.create_image_task", fake_create_image_task)
    return calls


def test_create_storyboard_frame_image_task_endpoint(db, fake_storyboard_image_creation):
    series, episode = _series_episode(db)

    resp = client.post(
        f"/api/storyboard-images/episodes/{episode.id}/frames/shot-001/tasks",
        json={"series_id": series.id},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["frame"]["frame_id"] == "shot-001"
    assert body["task"]["id"] == "task-shot-001"
    assert fake_storyboard_image_creation[0]["destination_role"] == "storyboard_frame"


def test_create_missing_storyboard_image_tasks_endpoint(db, fake_storyboard_image_creation):
    series, episode = _series_episode(db)

    resp = client.post(
        f"/api/storyboard-images/episodes/{episode.id}/tasks:batch",
        json={"series_id": series.id},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"] == {"created": 2, "skipped": 0, "failed": 0}
    assert [item["frame_id"] for item in body["results"]] == ["shot-001", "shot-002"]


def test_list_storyboard_image_state_endpoint(db):
    series, episode = _series_episode(db)

    resp = client.get(f"/api/storyboard-images/episodes/{episode.id}", params={"series_id": series.id})

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["summary"]["total"] == 2
    assert [frame["frame_id"] for frame in body["frames"]] == ["shot-001", "shot-002"]


def test_promote_storyboard_image_asset_endpoint(db):
    series, episode = _series_episode(db)
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="storyboard_ready",
        current_stage="storyboard_ready",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.flush()
    task = ImageCreationTask(
        id="task-1",
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="completed",
        series_id=series.id,
        episode_id=episode.id,
        prompt="prompt",
        destination_role="storyboard_frame",
        destination_context_json={"run_id": run.id, "frame_id": "shot-001"},
        count=1,
        target_count=1,
    )
    db.add(task)
    db.flush()
    asset = ImageCreationAsset(
        id="asset-approved",
        task_id=task.id,
        series_id=series.id,
        episode_id=episode.id,
        url="/static/image-creation/storyboard-approved.png",
        status="approved",
        version=1,
        destination_role="storyboard_frame",
        destination_context_json={"run_id": run.id, "frame_id": "shot-001"},
    )
    db.add(asset)
    db.commit()

    resp = client.post(
        f"/api/storyboard-images/assets/{asset.id}/promote",
        json={"run_id": run.id, "frame_id": "shot-001", "episode_id": episode.id, "asset_version": 1},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["video_asset"]["frame_id"] == "shot-001"
    assert body["video_asset"]["url"] == "/static/image-creation/storyboard-approved.png"


def test_promote_storyboard_image_asset_endpoint_rejects_cross_run_asset(db):
    series, episode = _series_episode(db)
    old_run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="storyboard_ready",
        current_stage="storyboard_ready",
        storyboard_json=episode.storyboard_json,
    )
    new_run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="storyboard_ready",
        current_stage="storyboard_ready",
        storyboard_json=episode.storyboard_json,
    )
    db.add_all([old_run, new_run])
    db.flush()
    task = ImageCreationTask(
        id="task-old-run-api",
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="completed",
        series_id=series.id,
        episode_id=episode.id,
        prompt="prompt",
        destination_role="storyboard_frame",
        destination_context_json={"run_id": old_run.id, "frame_id": "shot-001"},
        count=1,
        target_count=1,
    )
    db.add(task)
    db.flush()
    asset = ImageCreationAsset(
        id="asset-old-run-api",
        task_id=task.id,
        series_id=series.id,
        episode_id=episode.id,
        url="/static/image-creation/storyboard-old-run.png",
        status="approved",
        version=1,
        destination_role="storyboard_frame",
        destination_context_json={"run_id": old_run.id, "frame_id": "shot-001"},
    )
    db.add(asset)
    db.commit()

    resp = client.post(
        f"/api/storyboard-images/assets/{asset.id}/promote",
        json={"run_id": new_run.id, "frame_id": "shot-001", "episode_id": episode.id, "asset_version": 1},
    )

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_ASSET_SCOPE_CONFLICT"
    assert db.query(VideoProductionAsset).count() == 0


@pytest.mark.parametrize("stale_side", ["asset", "task"])
def test_promote_storyboard_image_asset_endpoint_rejects_split_context_mismatch(db, stale_side):
    series, episode = _series_episode(db)
    old_run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="storyboard_ready",
        current_stage="storyboard_ready",
        storyboard_json=episode.storyboard_json,
    )
    new_run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="storyboard_ready",
        current_stage="storyboard_ready",
        storyboard_json=episode.storyboard_json,
    )
    db.add_all([old_run, new_run])
    db.flush()
    old_context = {"run_id": old_run.id, "frame_id": "shot-001"}
    target_context = {"run_id": new_run.id, "frame_id": "shot-001"}
    task = ImageCreationTask(
        id=f"task-split-api-{stale_side}",
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="completed",
        series_id=series.id,
        episode_id=episode.id,
        prompt="prompt",
        destination_role="storyboard_frame",
        destination_context_json=old_context if stale_side == "task" else target_context,
        count=1,
        target_count=1,
    )
    db.add(task)
    db.flush()
    asset = ImageCreationAsset(
        id=f"asset-split-api-{stale_side}",
        task_id=task.id,
        series_id=series.id,
        episode_id=episode.id,
        url=f"/static/image-creation/split-api-{stale_side}.png",
        status="approved",
        version=1,
        destination_role="storyboard_frame",
        destination_context_json=old_context if stale_side == "asset" else target_context,
    )
    db.add(asset)
    db.commit()

    resp = client.post(
        f"/api/storyboard-images/assets/{asset.id}/promote",
        json={"run_id": new_run.id, "frame_id": "shot-001", "episode_id": episode.id, "asset_version": 1},
    )

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "IMAGE_ASSET_SCOPE_CONFLICT"
    assert db.query(VideoProductionAsset).count() == 0
