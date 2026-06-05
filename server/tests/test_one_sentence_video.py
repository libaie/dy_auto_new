from fastapi.testclient import TestClient
import pytest

from app.db_models import AgencyExpertInvocation, AIModel, Character, Episode, ProductionSegment, Scene, Series, VideoProductionRun
from app.main import app
from app.services.agency_runtime import AgencyRuntimeResult
from app.services.crypto import encrypt


def _expert_review_model(db):
    model = AIModel(
        name="One Sentence Expert Review",
        model_type="llm",
        provider="openai-compatible",
        base_url="https://llm.test/v1",
        api_key=encrypt("expert-key"),
        model_name="expert-review-model",
        enabled=True,
        config_json={
            "scene_key": "llm_agency_expert_review",
            "protocol": "openai_chat_completions",
        },
    )
    db.add(model)
    db.commit()
    return model


async def _agency_pass(self, **kwargs):
    return AgencyRuntimeResult(
        result_status="passed",
        output_summary={
            "decision": f"{kwargs['stage']} passed",
            "findings": [],
            "recommendations": [],
            "required_changes": [],
        },
        evidence=[],
        token_usage={},
        model_config_snapshot={"provider": "test"},
    )


async def _agency_block(self, **kwargs):
    return AgencyRuntimeResult(
        result_status="blocked",
        output_summary={
            "decision": f"{kwargs['stage']} blocked",
            "findings": ["missing locked references"],
            "recommendations": ["regenerate references"],
            "required_changes": ["add role and scene reference URLs"],
        },
        evidence=[{"type": "gate", "message": "blocked by test expert"}],
        token_usage={},
        model_config_snapshot={"provider": "test"},
    )


async def _fake_character_references(db, character_id, slot="all"):
    character = db.query(Character).filter_by(id=character_id).one()
    character.avatar_front_url = "/static/image-creation/character-front.png"
    character.avatar_side_url = "/static/image-creation/character-side.png"
    character.avatar_threequarter_url = "/static/image-creation/character-threequarter.png"
    character.avatar_fullbody_url = "/static/image-creation/character-fullbody.png"
    db.commit()
    db.refresh(character)
    return {
        "ok": True,
        "character": {"id": character.id},
        "generated": [
            {"slot": "avatar_front_url", "url": character.avatar_front_url},
            {"slot": "avatar_side_url", "url": character.avatar_side_url},
            {"slot": "avatar_threequarter_url", "url": character.avatar_threequarter_url},
            {"slot": "avatar_fullbody_url", "url": character.avatar_fullbody_url},
        ],
        "missing_assets": [],
    }


async def _fake_scene_references(db, scene_id, slot="all"):
    scene = db.query(Scene).filter_by(id=scene_id).one()
    scene.reference_wideshot_url = "/static/image-creation/scene-wide.png"
    scene.reference_midshot_url = "/static/image-creation/scene-mid.png"
    scene.reference_aerial_url = "/static/image-creation/scene-aerial.png"
    db.commit()
    db.refresh(scene)
    return {
        "ok": True,
        "scene": {"id": scene.id},
        "generated": [
            {"slot": "reference_wideshot_url", "url": scene.reference_wideshot_url},
            {"slot": "reference_midshot_url", "url": scene.reference_midshot_url},
            {"slot": "reference_aerial_url", "url": scene.reference_aerial_url},
        ],
        "missing_assets": [],
    }


def _mock_reference_generation(monkeypatch):
    monkeypatch.setattr(
        "app.services.reference_asset_service.generate_character_reference_images",
        _fake_character_references,
    )
    monkeypatch.setattr(
        "app.services.reference_asset_service.generate_scene_reference_images",
        _fake_scene_references,
    )


def test_one_sentence_video_creates_locked_storyboard_and_run(db, monkeypatch):
    _mock_reference_generation(monkeypatch)
    client = TestClient(app)

    resp = client.post("/api/video-production/one-sentence", json={
        "prompt": "一个年轻探险家在雨夜发现会发光的古地图，并决定追踪城市地下的秘密。",
        "target_duration_seconds": 60,
        "budget_limit": 1,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["agency_trace_status"] == "partial"
    assert body["agency_trace"]["style_lock"]["error_code"] == "EXPERT_MODEL_CONFIG_MISSING"
    assert body["agency_trace"]["storyboard"]["error_code"] == "EXPERT_MODEL_CONFIG_MISSING"
    assert body["route"] == f"/video-production/{body['run']['id']}"
    assert [step["key"] for step in body["steps"]] == [
        "prompt",
        "series",
        "style_lock",
        "storyboard",
        "production_plan",
        "image_generation",
        "image_review",
        "video_generation",
        "video_review",
        "compose",
        "final_review",
        "completed",
    ]

    series = db.query(Series).filter_by(id=body["series"]["id"]).one()
    episode = db.query(Episode).filter_by(id=body["episode"]["id"]).one()
    run = db.query(VideoProductionRun).filter_by(id=body["run"]["id"]).one()

    assert series.logline.startswith("一个年轻探险家")
    assert series.story_bible_json["style_lock"]["locked"] is True
    assert series.story_bible_json["style_lock"]["source"] == "one_sentence"
    assert series.story_bible_json["style_lock"]["agency_trace"]["error_code"] == "EXPERT_MODEL_CONFIG_MISSING"
    assert episode.storyboard_json["frame_count"] == 8
    assert sum(frame["duration"] for frame in episode.storyboard_json["frames"]) == 60
    assert all(frame["duration"] <= 8 for frame in episode.storyboard_json["frames"])
    assert episode.storyboard_json["agency_trace"]["error_code"] == "EXPERT_MODEL_CONFIG_MISSING"
    frame = episode.storyboard_json["frames"][0]
    assert frame["character_ids"]
    assert frame["scene_id"]
    assert frame["image_prompt"]
    assert frame["video_prompt"]
    assert frame["duration"] == 8
    assert run.production_link_status == "linked"
    assert run.status == "storyboard_ready"
    assert db.query(ProductionSegment).count() == 8


def test_one_sentence_video_splits_15_second_smoke_into_multiple_shots(db, monkeypatch):
    _mock_reference_generation(monkeypatch)
    client = TestClient(app)

    resp = client.post("/api/video-production/one-sentence", json={
        "prompt": "A detective follows a red paper crane from a rainy neon street into a close-up reveal.",
        "target_duration_seconds": 15,
        "budget_limit": 1,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    body = resp.json()
    episode = db.query(Episode).filter_by(id=body["episode"]["id"]).one()
    storyboard = episode.storyboard_json

    assert storyboard["frame_count"] == 3
    assert [frame["duration"] for frame in storyboard["frames"]] == [5, 5, 5]
    assert [frame["shot_type"] for frame in storyboard["frames"]] == ["wide", "medium", "close_up"]
    assert [frame["action"] for frame in storyboard["frames"]] == [
        "opening hook",
        "investigation beat",
        "close-up reveal and audience question",
    ]
    assert len({frame["narration"] for frame in storyboard["frames"]}) == 3
    assert all(frame["bgm_direction"] for frame in storyboard["frames"])


def test_one_sentence_video_injects_reference_assets_into_style_storyboard_and_segments(db, monkeypatch):
    _expert_review_model(db)
    _mock_reference_generation(monkeypatch)
    monkeypatch.setattr("app.services.agency_runtime.AgencySkillRuntime.invoke", _agency_pass)
    client = TestClient(app)

    resp = client.post("/api/video-production/one-sentence", json={
        "prompt": "A forensic host enters an abandoned theater and finds the same actress appearing in every mirror.",
        "target_duration_seconds": 60,
        "budget_limit": 1,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    body = resp.json()
    series = db.query(Series).filter_by(id=body["series"]["id"]).one()
    episode = db.query(Episode).filter_by(id=body["episode"]["id"]).one()
    style_lock = series.story_bible_json["style_lock"]
    character_refs = style_lock["characters"][0]["reference_urls"]
    scene_refs = style_lock["scenes"][0]["reference_urls"]

    assert style_lock["agency_team"]["enabled"] is True
    assert character_refs
    assert scene_refs
    assert style_lock["visual_style"]["reference_urls"] == scene_refs[:3]
    frame = episode.storyboard_json["frames"][0]
    assert frame["reference_urls"]
    assert frame["character_reference_urls"] == character_refs[:9]
    assert frame["style_reference_urls"] == scene_refs[:3]
    assert "@Image 1" in frame["reference_instructions"]
    segments = db.query(ProductionSegment).all()
    assert segments
    assert all(segment.reference_roles_json for segment in segments)


def test_one_sentence_video_infers_live_action_style_from_reality_health_prompt(db, monkeypatch):
    _expert_review_model(db)
    _mock_reference_generation(monkeypatch)
    monkeypatch.setattr("app.services.agency_runtime.AgencySkillRuntime.invoke", _agency_pass)
    client = TestClient(app)

    resp = client.post("/api/video-production/one-sentence", json={
        "prompt": "《控糖日记》：一位现实生活的普通中老年人老刘用现实真实生活方式管理血糖，每集解决一个日常控糖问题。",
        "target_duration_seconds": 60,
        "budget_limit": 1,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    body = resp.json()
    series = db.query(Series).filter_by(id=body["series"]["id"]).one()
    episode = db.query(Episode).filter_by(id=body["episode"]["id"]).one()
    style_lock = series.story_bible_json["style_lock"]

    assert style_lock["visual_style"]["medium"] == "photorealistic_live_action"
    assert "photorealistic live-action" in style_lock["visual_style"]["prompt"]
    assert "no anime" in style_lock["visual_style"]["negative_prompt"]
    assert "photorealistic live-action" in episode.storyboard_json["frames"][0]["image_prompt"]
    assert "no cartoon" in episode.storyboard_json["frames"][0]["image_prompt"]


def test_one_sentence_video_blocks_when_style_or_storyboard_expert_blocks(db, monkeypatch):
    _expert_review_model(db)
    _mock_reference_generation(monkeypatch)
    monkeypatch.setattr("app.services.agency_runtime.AgencySkillRuntime.invoke", _agency_block)
    monkeypatch.setattr(
        "app.services.production_run_service.start_image_stage",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("image stage must not start")),
    )
    client = TestClient(app)

    resp = client.post("/api/video-production/one-sentence", json={
        "prompt": "A painter discovers her unfinished mural is changing the city outside.",
        "target_duration_seconds": 60,
        "budget_limit": 1,
        "autostart_images": True,
    })

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "REVIEW_GATE_BLOCKED"
    assert detail["repair_action"]
    assert detail["affected_ids"]
    assert db.query(VideoProductionRun).filter_by(status="image_batch_running").count() == 0


def test_one_sentence_real_provider_accepts_long_duration_after_shot_segmentation(db, monkeypatch):
    _expert_review_model(db)
    _mock_reference_generation(monkeypatch)
    monkeypatch.setattr("app.services.agency_runtime.AgencySkillRuntime.invoke", _agency_pass)
    client = TestClient(app)

    resp = client.post("/api/video-production/one-sentence", json={
        "prompt": "A courier crosses five districts to deliver a memory chip before dawn.",
        "target_duration_seconds": 120,
        "budget_limit": 1,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    body = resp.json()
    episode = db.query(Episode).filter_by(id=body["episode"]["id"]).one()
    assert episode.storyboard_json["total_duration"] == 120
    assert sum(frame["duration"] for frame in episode.storyboard_json["frames"]) == 120
    assert episode.storyboard_json["frame_count"] > 3


def test_one_sentence_real_provider_accepts_28800_second_upper_bound_with_short_segments(db, monkeypatch):
    _expert_review_model(db)
    _mock_reference_generation(monkeypatch)
    monkeypatch.setattr("app.services.agency_runtime.AgencySkillRuntime.invoke", _agency_pass)
    client = TestClient(app)

    resp = client.post("/api/video-production/one-sentence", json={
        "prompt": "A serialized mystery follows one archivist across a whole night of linked investigations.",
        "target_duration_seconds": 28800,
        "budget_limit": 1,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    body = resp.json()
    episode = db.query(Episode).filter_by(id=body["episode"]["id"]).one()
    segments = db.query(ProductionSegment).all()
    assert episode.storyboard_json["total_duration"] == 28800
    assert episode.storyboard_json["frame_count"] == 3600
    assert episode.storyboard_json["materialized_frame_count"] <= 120
    assert len(episode.storyboard_json["frames"]) == episode.storyboard_json["materialized_frame_count"]
    assert sum(frame["duration"] for frame in episode.storyboard_json["frames"]) == episode.storyboard_json["materialized_duration"]
    assert episode.storyboard_json["storyboard_window"]["remaining_frame_count"] > 0
    assert episode.storyboard_json["storyboard_window"]["remaining_duration"] > 0
    assert segments
    assert len(segments) == episode.storyboard_json["materialized_frame_count"]
    assert all(float(segment.duration_seconds) <= 8 for segment in segments)


def test_one_sentence_video_autostarts_image_stage(db, monkeypatch):
    _mock_reference_generation(monkeypatch)

    async def fake_start_image_stage(db, run_id):
        run = db.query(VideoProductionRun).filter_by(id=run_id).one()
        assert run.status == "storyboard_ready"
        assert run.current_stage == "storyboard_ready"
        assert run.model_trace_json["autopilot"]["enabled"] is True
        assert run.model_trace_json["autopilot"]["source"] == "one_sentence"
        run.status = "image_batch_running"
        run.current_stage = "image_generation"
        run.pixelle_stage_task_id = "image-task"
        db.commit()
        db.refresh(run)
        return run

    monkeypatch.setattr("app.services.production_run_service.start_image_stage", fake_start_image_stage)
    client = TestClient(app)

    resp = client.post("/api/video-production/one-sentence", json={
        "prompt": "雨夜里，外卖骑手偶然救下一位失忆的 AI 歌手。",
        "target_duration_seconds": 60,
        "budget_limit": 1,
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["run"]["status"] == "image_batch_running"
    assert body["run"]["model_trace_json"]["autopilot"]["enabled"] is True
    assert body["run"]["model_trace_json"]["autopilot"]["source"] == "one_sentence"
    steps = {step["key"]: step for step in body["steps"]}
    assert steps["image_generation"]["status"] == "running"
    assert steps["image_review"]["status"] == "pending"


def test_one_sentence_video_links_style_and_storyboard_invocations_to_run(db, monkeypatch):
    _expert_review_model(db)
    _mock_reference_generation(monkeypatch)
    monkeypatch.setattr("app.services.agency_runtime.AgencySkillRuntime.invoke", _agency_pass)
    client = TestClient(app)

    resp = client.post("/api/video-production/one-sentence", json={
        "prompt": "一名纪录片导演追踪城市里即将消失的老手艺。",
        "target_duration_seconds": 60,
        "budget_limit": 1,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    body = resp.json()
    run_id = body["run"]["id"]
    invocations = (
        db.query(AgencyExpertInvocation)
        .filter(AgencyExpertInvocation.series_id == body["series"]["id"])
        .all()
    )
    assert invocations
    assert {"style_lock", "storyboard"}.issubset({item.stage for item in invocations})
    assert {item.run_id for item in invocations} == {run_id}


@pytest.mark.asyncio
async def test_one_sentence_reference_generation_timeout_returns_pending_run(db, monkeypatch):
    from app.services.one_sentence_video_service import create_one_sentence_video

    async def slow_character_references(db, character_id, slot="all"):
        import asyncio

        await asyncio.sleep(1)
        return {"ok": True}

    async def slow_scene_references(db, scene_id, slot="all"):
        import asyncio

        await asyncio.sleep(1)
        return {"ok": True}

    monkeypatch.setattr("app.services.one_sentence_video_service.ONE_SENTENCE_REFERENCE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(
        "app.services.reference_asset_service.generate_character_reference_images",
        slow_character_references,
    )
    monkeypatch.setattr(
        "app.services.reference_asset_service.generate_scene_reference_images",
        slow_scene_references,
    )
    result = await create_one_sentence_video(
        db,
        prompt="A realistic diabetes education host explains a simple breakfast choice.",
        target_duration_seconds=60,
        budget_limit=1,
        autostart_images=False,
    )

    series = db.query(Series).filter_by(id=result["series"].id).one()
    style_lock = series.story_bible_json["style_lock"]
    assert style_lock["reference_generation_trace"]["error_code"] == "REFERENCE_GENERATION_TIMEOUT"
    assert result["run"].status == "reference_generation_running"
    assert result["background_reference_pending"] is True


@pytest.mark.asyncio
async def test_one_sentence_background_reference_completion_refreshes_storyboard_and_segments(db, monkeypatch):
    from app.services.one_sentence_video_service import (
        complete_one_sentence_reference_generation,
        create_one_sentence_video,
    )

    async def slow_character_references(db, character_id, slot="all"):
        import asyncio

        await asyncio.sleep(1)
        return {"ok": True}

    async def slow_scene_references(db, scene_id, slot="all"):
        import asyncio

        await asyncio.sleep(1)
        return {"ok": True}

    monkeypatch.setattr("app.services.one_sentence_video_service.ONE_SENTENCE_REFERENCE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(
        "app.services.reference_asset_service.generate_character_reference_images",
        slow_character_references,
    )
    monkeypatch.setattr(
        "app.services.reference_asset_service.generate_scene_reference_images",
        slow_scene_references,
    )
    result = await create_one_sentence_video(
        db,
        prompt="A realistic diabetes education host explains a simple breakfast choice.",
        target_duration_seconds=60,
        budget_limit=1,
        autostart_images=False,
    )
    run_id = result["run"].id

    _mock_reference_generation(monkeypatch)
    completed = await complete_one_sentence_reference_generation(db, run_id, autostart_images=False)

    assert completed.status == "storyboard_ready"
    series = db.query(Series).filter_by(id=completed.series_id).one()
    episode = db.query(Episode).filter_by(id=completed.episode_id).one()
    style_lock = series.story_bible_json["style_lock"]
    assert style_lock["reference_generation_trace"]["stage_status"] == "complete"
    assert style_lock["characters"][0]["reference_urls"]
    assert style_lock["scenes"][0]["reference_urls"]
    assert episode.storyboard_json["frames"][0]["reference_urls"]
    assert all(segment.reference_roles_json for segment in db.query(ProductionSegment).all())


def test_one_sentence_reference_generation_running_readiness_has_no_review_blocks(db):
    from app.services.video_production_readiness import build_run_readiness

    series = Series(
        title="Reference readiness",
        logline="Reference readiness",
        genre="health",
        total_episodes=1,
        target_duration=60,
        story_bible_json={"style_lock": {"locked": True}},
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={"frames": [{"frame_id": "shot-001", "duration": 5}]},
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type="real_short_e2e",
        status="reference_generation_running",
        current_stage="reference_generation",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.commit()

    readiness = build_run_readiness(db, run)

    assert readiness["next_action"]["key"] == "wait_reference_generation"
    assert readiness["needs_review"] is False
    assert readiness["blocks"] == []


@pytest.mark.asyncio
async def test_reference_generation_error_does_not_overwrite_progressed_image_stage(db, monkeypatch):
    from app.services.one_sentence_video_service import (
        complete_one_sentence_reference_generation,
        create_one_sentence_video,
    )

    _mock_reference_generation(monkeypatch)

    result = await create_one_sentence_video(
        db,
        prompt="A real diabetes educator prepares a calm morning routine.",
        target_duration_seconds=60,
        budget_limit=1,
        autostart_images=False,
    )
    run = result["run"]
    run.status = "image_batch_running"
    run.current_stage = "image_generation"
    run.error_message = None
    db.commit()

    async def failing_character_references(db, character_id, slot="all"):
        raise RuntimeError("late duplicate reference task failed")

    monkeypatch.setattr(
        "app.services.reference_asset_service.generate_character_reference_images",
        failing_character_references,
    )

    completed = await complete_one_sentence_reference_generation(db, run.id, autostart_images=True)

    assert completed.status == "image_batch_running"
    assert completed.current_stage == "image_generation"
    assert completed.error_message is None


def test_one_sentence_storyboard_ready_readiness_can_start_images_without_review_blocks(db):
    from app.services.video_production_readiness import build_run_readiness

    series = Series(
        title="Storyboard readiness",
        logline="Storyboard readiness",
        genre="health",
        total_episodes=1,
        target_duration=60,
        story_bible_json={"style_lock": {"locked": True}},
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={"frames": [{"frame_id": "shot-001", "duration": 5}]},
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type="real_short_e2e",
        status="storyboard_ready",
        current_stage="storyboard_ready",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.commit()

    readiness = build_run_readiness(db, run)

    assert readiness["next_action"]["key"] == "start_images"
    assert readiness["can_start_images"] is True
    assert readiness["needs_review"] is False
    assert readiness["blocks"] == []


def test_one_sentence_expert_review_timeout_returns_partial_trace(db, monkeypatch):
    _expert_review_model(db)
    _mock_reference_generation(monkeypatch)

    async def slow_style_lock_review(self, *args, **kwargs):
        import asyncio

        await asyncio.sleep(1)
        return {"stage": "style_lock", "stage_status": "passed"}

    async def slow_storyboard_review(self, *args, **kwargs):
        import asyncio

        await asyncio.sleep(1)
        return {"stage": "storyboard", "stage_status": "passed"}

    monkeypatch.setattr("app.services.one_sentence_video_service.ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(
        "app.services.one_sentence_video_service.AgencyOrchestrator.run_style_lock_review",
        slow_style_lock_review,
    )
    monkeypatch.setattr(
        "app.services.one_sentence_video_service.AgencyOrchestrator.run_storyboard_review",
        slow_storyboard_review,
    )
    client = TestClient(app)

    resp = client.post("/api/video-production/one-sentence", json={
        "prompt": "A realistic diabetes education host explains a simple breakfast choice.",
        "target_duration_seconds": 60,
        "budget_limit": 1,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["agency_trace"]["style_lock"]["error_code"] == "ONE_SENTENCE_STYLE_REVIEW_TIMEOUT"
    assert body["agency_trace"]["storyboard"]["error_code"] == "ONE_SENTENCE_STORYBOARD_REVIEW_TIMEOUT"
    assert body["agency_trace_status"] == "partial"
