from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config import bj_now
from app.db_models import Episode, ImageCreationAsset, ImageCreationTask, Series, VideoProductionAsset, VideoProductionRun


def _series_episode(db, *, storyboard: dict | None = None):
    series = Series(
        title="Storyboard Images",
        logline="One precise story becomes visual production frames.",
        status="active",
        target_duration=4,
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Episode 1",
        duration_seconds=4,
        storyboard_json=storyboard or {
            "frames": [
                {
                    "frame_id": "shot-001",
                    "time_range": "0-2秒",
                    "duration": 2,
                    "image_prompt": "时间段: 0-2秒\n主体/角色: 老李\n画面动作: 老李抬头看向早餐。",
                    "negative_prompt": "no blur",
                    "reference_urls": ["/static/characters/laoli-front.png"],
                },
                {
                    "frame_id": "shot-002",
                    "time_range": "2-4秒",
                    "duration": 2,
                    "image_prompt": "时间段: 2-4秒\n主体/角色: 老李\n画面动作: 老李把早餐推远。",
                    "reference_urls": ["/static/scenes/clinic.png"],
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
        negative_prompt=payload.get("negative_prompt") or "",
        reference_images_json=payload.get("reference_images") or [],
        destination_role=payload["destination_role"],
        destination_context_json=payload["destination_context"],
        count=payload.get("count") or 1,
        target_count=payload.get("count") or 1,
        cost_status="estimated",
        request_json={},
        estimated_cost_json={},
        created_at=bj_now(),
    )


@pytest.mark.asyncio
async def test_create_storyboard_frame_image_task_builds_image_creation_payload(db, monkeypatch):
    from app.services import storyboard_image_service

    series, episode = _series_episode(db)
    captured = {}

    async def fake_create_image_task(db_session, payload):
        captured.update(payload)
        return _task_from_payload(payload)

    monkeypatch.setattr(storyboard_image_service, "create_image_task", fake_create_image_task)
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="storyboard_ready",
        current_stage="storyboard_ready",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.commit()

    result = await storyboard_image_service.create_storyboard_frame_image_task(
        db,
        series_id=series.id,
        episode_id=episode.id,
        frame_id="shot-001",
        run_id=run.id,
        user_id="user-1",
    )

    assert captured["mode"] == "text_to_image"
    assert captured["destination_role"] == "storyboard_frame"
    assert captured["destination_context"]["frame_id"] == "shot-001"
    assert captured["destination_context"]["time_range"] == "0-2秒"
    assert captured["destination_context"]["run_id"] == run.id
    assert captured["reference_images"][0]["url"] == "/static/characters/laoli-front.png"
    assert captured["negative_prompt"] == "no blur"
    assert captured["idempotency_key"].startswith("storyboard-frame-image:")
    assert result["frame"]["frame_id"] == "shot-001"
    assert result["task"]["id"] == "task-shot-001"


def test_force_storyboard_frame_image_payload_uses_fresh_idempotency_key(db):
    from app.services.storyboard_image_service import _frame_payload

    series, episode = _series_episode(db)
    frame = episode.storyboard_json["frames"][0]

    first = _frame_payload(
        series_id=series.id,
        episode_id=episode.id,
        run_id="run-1",
        frame={**frame, "frame_id": "shot-001"},
        force=True,
        count=1,
        size=None,
        user_id="user-1",
    )
    second = _frame_payload(
        series_id=series.id,
        episode_id=episode.id,
        run_id="run-1",
        frame={**frame, "frame_id": "shot-001"},
        force=True,
        count=1,
        size=None,
        user_id="user-1",
    )

    assert first["idempotency_key"] != second["idempotency_key"]


@pytest.mark.asyncio
async def test_force_storyboard_frame_image_task_creates_fresh_task(db, monkeypatch):
    from app.services import storyboard_image_service

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
    frame = episode.storyboard_json["frames"][0]
    base_key = storyboard_image_service._task_idempotency_key(
        series_id=series.id,
        episode_id=episode.id,
        frame_id="shot-001",
        prompt=frame["image_prompt"],
        reference_images=storyboard_image_service._frame_reference_images(frame),
        run_id=run.id,
    )
    old_force_key = f"{base_key}:force:{storyboard_image_service._stable_hash({'count': 1, 'size': None, 'user_id': 'user-1'})}"
    existing = ImageCreationTask(
        id="existing-force-task",
        idempotency_key=old_force_key,
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="running",
        series_id=series.id,
        episode_id=episode.id,
        prompt=frame["image_prompt"],
        destination_role="storyboard_frame",
        destination_context_json={"run_id": run.id, "frame_id": "shot-001"},
        count=1,
        target_count=1,
    )
    db.add(existing)
    db.commit()
    created_payloads = []

    async def fake_create_image_task(db_session, payload):
        if payload["idempotency_key"] == old_force_key:
            return existing
        created_payloads.append(payload)
        return _task_from_payload(payload)

    monkeypatch.setattr(storyboard_image_service, "create_image_task", fake_create_image_task)

    result = await storyboard_image_service.create_storyboard_frame_image_task(
        db,
        series_id=series.id,
        episode_id=episode.id,
        frame_id="shot-001",
        run_id=run.id,
        force=True,
        user_id="user-1",
    )

    assert created_payloads
    assert created_payloads[0]["idempotency_key"] != old_force_key
    assert result["frame"]["status"] == "created"
    assert result["task"]["id"] != existing.id


@pytest.mark.asyncio
async def test_create_missing_storyboard_image_tasks_returns_per_frame_results(db, monkeypatch):
    from app.services import storyboard_image_service

    series, episode = _series_episode(db)

    async def fake_create_image_task(db_session, payload):
        return _task_from_payload(payload)

    monkeypatch.setattr(storyboard_image_service, "create_image_task", fake_create_image_task)

    result = await storyboard_image_service.create_missing_storyboard_image_tasks(
        db,
        series_id=series.id,
        episode_id=episode.id,
    )

    assert result["summary"] == {"created": 2, "skipped": 0, "failed": 0}
    assert [item["frame_id"] for item in result["results"]] == ["shot-001", "shot-002"]
    assert {item["status"] for item in result["results"]} == {"created"}


def test_list_storyboard_image_state_returns_frames_in_storyboard_order(db):
    from app.services.storyboard_image_service import list_storyboard_image_state

    series, episode = _series_episode(db)
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
        destination_context_json={
            "series_id": series.id,
            "episode_id": episode.id,
            "frame_id": "shot-001",
            "time_range": "0-2秒",
        },
        count=1,
        target_count=1,
    )
    db.add(task)
    db.flush()
    db.add(ImageCreationAsset(
        id="asset-1",
        task_id=task.id,
        series_id=series.id,
        episode_id=episode.id,
        url="/static/image-creation/storyboard-1.png",
        status="approved",
        version=1,
        destination_role="storyboard_frame",
        destination_context_json={
            "series_id": series.id,
            "episode_id": episode.id,
            "frame_id": "shot-001",
            "time_range": "0-2秒",
        },
    ))
    db.commit()

    state = list_storyboard_image_state(db, series_id=series.id, episode_id=episode.id)

    assert [frame["frame_id"] for frame in state["frames"]] == ["shot-001", "shot-002"]
    assert state["frames"][0]["status"] == "approved"
    assert state["frames"][0]["asset"]["id"] == "asset-1"
    assert state["frames"][1]["status"] == "missing"
    assert state["summary"] == {"total": 2, "approved": 1, "pending": 0, "running": 0, "missing": 1, "blocked": 0}


def test_storyboard_image_state_is_scoped_by_run_id(db):
    from app.services.storyboard_image_service import list_storyboard_image_state

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
        id="task-old-run",
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="completed",
        series_id=series.id,
        episode_id=episode.id,
        prompt="prompt",
        destination_role="storyboard_frame",
        destination_context_json={
            "series_id": series.id,
            "episode_id": episode.id,
            "run_id": old_run.id,
            "frame_id": "shot-001",
            "time_range": "0-2秒",
        },
        count=1,
        target_count=1,
    )
    db.add(task)
    db.flush()
    db.add(ImageCreationAsset(
        id="asset-old-run",
        task_id=task.id,
        series_id=series.id,
        episode_id=episode.id,
        url="/static/image-creation/old-run.png",
        status="approved",
        version=1,
        destination_role="storyboard_frame",
        destination_context_json={
            "series_id": series.id,
            "episode_id": episode.id,
            "run_id": old_run.id,
            "frame_id": "shot-001",
            "time_range": "0-2秒",
        },
    ))
    db.commit()

    new_run_state = list_storyboard_image_state(
        db,
        series_id=series.id,
        episode_id=episode.id,
        run_id=new_run.id,
    )
    old_run_state = list_storyboard_image_state(
        db,
        series_id=series.id,
        episode_id=episode.id,
        run_id=old_run.id,
    )

    assert new_run_state["frames"][0]["status"] == "missing"
    assert new_run_state["frames"][0]["asset"] is None
    assert old_run_state["frames"][0]["status"] == "approved"
    assert old_run_state["frames"][0]["asset"]["id"] == "asset-old-run"


def test_promote_storyboard_image_asset_blocks_unapproved_assets(db):
    from app.services.storyboard_image_service import promote_storyboard_image_asset

    series, episode = _series_episode(db)
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="storyboard_ready",
        current_stage="storyboard_ready",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
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
        id="asset-pending",
        task_id=task.id,
        series_id=series.id,
        episode_id=episode.id,
        url="/static/image-creation/pending.png",
        status="review_pending",
        version=1,
        destination_role="storyboard_frame",
        destination_context_json={"run_id": run.id, "frame_id": "shot-001"},
    )
    db.add(asset)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        promote_storyboard_image_asset(
            db,
            asset_id=asset.id,
            run_id=run.id,
            frame_id="shot-001",
            episode_id=episode.id,
            asset_version=1,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["error_code"] == "STORYBOARD_IMAGE_REVIEW_REQUIRED"


def test_promote_storyboard_image_asset_promotes_same_run_asset(db):
    from app.services.storyboard_image_service import promote_storyboard_image_asset

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
        id="task-promote-happy",
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
        id="asset-promote-happy",
        task_id=task.id,
        series_id=series.id,
        episode_id=episode.id,
        url="/static/image-creation/storyboard-happy.png",
        status="approved",
        version=1,
        destination_role="storyboard_frame",
        destination_context_json={"run_id": run.id, "frame_id": "shot-001"},
    )
    db.add(asset)
    db.commit()

    result = promote_storyboard_image_asset(
        db,
        asset_id=asset.id,
        run_id=run.id,
        frame_id="shot-001",
        episode_id=episode.id,
        asset_version=1,
    )

    video_asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.run_id == run.id).one()
    assert result["ok"] is True
    assert result["video_asset"]["id"] == video_asset.id
    assert result["video_asset"]["frame_id"] == "shot-001"
    assert video_asset.url == "/static/image-creation/storyboard-happy.png"


def test_promote_storyboard_image_asset_rejects_cross_run_assets(db):
    from app.services.storyboard_image_service import promote_storyboard_image_asset

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
        id="task-old-run-promote",
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
        id="asset-old-run-promote",
        task_id=task.id,
        series_id=series.id,
        episode_id=episode.id,
        url="/static/image-creation/old-run-promote.png",
        status="approved",
        version=1,
        destination_role="storyboard_frame",
        destination_context_json={"run_id": old_run.id, "frame_id": "shot-001"},
    )
    db.add(asset)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        promote_storyboard_image_asset(
            db,
            asset_id=asset.id,
            run_id=new_run.id,
            frame_id="shot-001",
            episode_id=episode.id,
            asset_version=1,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["error_code"] == "IMAGE_ASSET_SCOPE_CONFLICT"
    assert db.query(VideoProductionAsset).count() == 0


@pytest.mark.parametrize("stale_side", ["asset", "task"])
def test_promote_storyboard_image_asset_rejects_split_context_mismatch(db, stale_side):
    from app.services.storyboard_image_service import promote_storyboard_image_asset

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
        id=f"task-split-{stale_side}",
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
        id=f"asset-split-{stale_side}",
        task_id=task.id,
        series_id=series.id,
        episode_id=episode.id,
        url=f"/static/image-creation/split-{stale_side}.png",
        status="approved",
        version=1,
        destination_role="storyboard_frame",
        destination_context_json=old_context if stale_side == "asset" else target_context,
    )
    db.add(asset)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        promote_storyboard_image_asset(
            db,
            asset_id=asset.id,
            run_id=new_run.id,
            frame_id="shot-001",
            episode_id=episode.id,
            asset_version=1,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["error_code"] == "IMAGE_ASSET_SCOPE_CONFLICT"
    assert db.query(VideoProductionAsset).count() == 0
