"""Style-lock, auto-plan, and pipeline persistence tests."""
import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.domains.ai_video_series import story_planning, style_lock
from app.main import app
from app.db_models import AIModel, AITextArtifact, Character, Episode, GeneratedVideo, PipelineRun, ProductionJob, Scene, Series
from app.services.agency_runtime import AgencyRuntimeResult
from app.services.crypto import encrypt


def _expert_review_model(db):
    model = AIModel(
        name="Series Pipeline Expert Review",
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
            "scorecard": {
                "overall_score": 95,
                "pass_threshold": 80,
                "verdict": "pass",
                "dimensions": [{"key": "quality", "score": 95, "threshold": 80}],
                "repair_intent": "none",
                "confidence": 0.9,
            },
        },
        evidence=[],
        token_usage={},
        model_config_snapshot={"provider": "test"},
    )


def test_auto_plan_splits_long_video_into_seedance_shots_with_anchors():
    from app.routers.director import _normalize_auto_frames

    character_refs = [f"https://cdn.test/lin-angle-{index}.png" for index in range(1, 11)]
    scene_refs = [f"https://cdn.test/clinic-style-{index}.png" for index in range(1, 5)]
    style_lock = {
        "visual_style": {"prompt": "cyber-noir, rainy neon, consistent cool palette"},
        "characters": [{"id": "char-1", "name": "Lin", "reference_urls": character_refs}],
        "scenes": [{"id": "scene-1", "name": "Rain Clinic", "reference_urls": scene_refs}],
    }

    frames = _normalize_auto_frames([{
        "narration": "Lin crosses the clinic and finds the hidden signal.",
        "image_prompt": "Lin investigates the rain-lit clinic.",
        "action": "crosses the clinic and opens a hidden panel",
        "emotion": "tense but focused",
    }], style_lock, target_duration=72)

    assert len(frames) == 9
    assert round(sum(frame["duration"] for frame in frames), 2) == 72
    assert all(frame["duration"] <= 8 for frame in frames)
    assert frames[0]["shot_type"] == "wide"
    assert frames[1]["shot_type"] == "medium"
    assert frames[2]["shot_type"] == "close_up"
    assert frames[0]["character_reference_urls"] == character_refs[:9]
    assert frames[0]["style_reference_urls"] == scene_refs[:3]
    assert frames[0]["reference_urls"] == character_refs[:9] + scene_refs[:3]
    assert "@Image 1" in frames[0]["image_prompt"]
    assert "face, hairstyle, outfit" in frames[0]["reference_instructions"]
    assert frames[0]["action"] == "crosses the clinic and opens a hidden panel"
    assert frames[0]["emotion"] == "tense but focused"
    assert "previous segment end frame" in frames[1]["continuity_notes"]


@pytest.fixture
def client():
    return TestClient(app)


def _create_series(db, *, with_episode=True):
    series = Series(
        title="City Healer",
        logline="A young doctor solves urban mysteries with a consistent cyber-noir style.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    episode = None
    if with_episode:
        episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
        db.add(episode)
    db.commit()
    return series, episode


@pytest.mark.asyncio
async def test_style_lock_fills_multi_angle_character_and_scene_references(db, monkeypatch):
    from app.routers import series as series_router

    parent = Series(title="Anchors", logline="Test", genre="drama")
    character = Character(
        name="Lin",
        appearance_desc="short black hair",
        outfit_desc="gray coat",
    )
    scene = Scene(
        name="Rain Clinic",
        location_desc="neon clinic",
        lighting="cool neon",
        mood="tense",
    )
    db.add_all([parent, character, scene])
    db.flush()
    parent.characters.append(character)
    parent.scenes.append(scene)

    calls = []

    async def fake_generate_reference_image(db_session, prompt, **kwargs):
        calls.append(prompt)
        return f"https://cdn.test/ref-{len(calls)}.png"

    monkeypatch.setattr(style_lock, "generate_reference_image", fake_generate_reference_image)

    missing = await series_router._fill_reference_assets(parent, db)

    assert missing == []
    assert series_router._character_reference_urls(character) == [
        "https://cdn.test/ref-1.png",
        "https://cdn.test/ref-3.png",
        "https://cdn.test/ref-2.png",
        "https://cdn.test/ref-4.png",
    ]
    assert series_router._scene_reference_urls(scene) == [
        "https://cdn.test/ref-5.png",
        "https://cdn.test/ref-6.png",
        "https://cdn.test/ref-7.png",
    ]
    assert "three-quarter character anchor" in calls[1]
    assert "mid-shot scene lighting" in calls[5]
    scene_prompts = calls[4:]
    assert len(scene_prompts) == 3
    for prompt in scene_prompts:
        lowered = prompt.lower()
        assert "empty environment plate" in lowered
        assert "no people" in lowered
        assert "no humans" in lowered
        assert "no characters" in lowered


@pytest.mark.asyncio
async def test_style_lock_infers_live_action_style_from_reality_health_logline(db, monkeypatch):
    from app.routers import series as series_router

    parent = Series(
        title="控糖日记",
        logline="一位现实生活的普通中老年人老刘用现实真实生活方式管理血糖，每集解决一个日常控糖问题。",
        genre="health",
    )
    character = Character(
        name="老刘",
        appearance_desc="普通中老年男性，生活化，不夸张",
        outfit_desc="浅色 polo 衫和深色长裤",
    )
    scene = Scene(
        name="家庭餐桌",
        location_desc="普通居民家中的餐桌",
        lighting="自然 daylight",
        mood="生活化",
    )
    db.add_all([parent, character, scene])
    db.flush()
    parent.characters.append(character)
    parent.scenes.append(scene)
    db.commit()

    calls = []

    async def fake_generate_reference_image(db_session, prompt, **kwargs):
        calls.append(prompt)
        return f"https://cdn.test/ref-{len(calls)}.png"

    monkeypatch.setattr(style_lock, "generate_reference_image", fake_generate_reference_image)

    missing = await series_router._fill_reference_assets(parent, db)
    story_bible = series_router._build_story_bible(parent, version=1, missing_assets=missing)
    visual_style = story_bible["style_lock"]["visual_style"]

    assert visual_style["medium"] == "photorealistic_live_action"
    assert "photorealistic live-action" in visual_style["prompt"]
    assert "no anime" in visual_style["negative_prompt"]
    assert calls
    assert all("photorealistic live-action" in prompt for prompt in calls)
    assert all("no cartoon" in prompt for prompt in calls)


@pytest.mark.asyncio
async def test_style_lock_regenerates_usable_references_when_inferred_medium_changes(db, monkeypatch):
    from app.routers import series as series_router

    parent = Series(
        title="控糖日记",
        logline="一位现实生活的普通中老年人老刘用现实真实生活方式管理血糖。",
        genre="health",
    )
    character = Character(
        name="老刘",
        appearance_desc="普通中老年男性",
        outfit_desc="浅色 polo 衫",
        avatar_front_url="https://cdn.test/old-cartoon-front.png",
        meta_json={
            "reference_generation": {
                "avatar_front_url": {
                    "prompt": "front-view character anchor sheet, stylized character design",
                    "url": "https://cdn.test/old-cartoon-front.png",
                }
            }
        },
    )
    scene = Scene(
        name="家庭餐桌",
        location_desc="普通居民家中的餐桌",
        reference_wideshot_url="https://cdn.test/old-scene.png",
        meta_json={
            "reference_generation": {
                "reference_wideshot_url": {
                    "prompt": "wide establishing scene reference",
                    "url": "https://cdn.test/old-scene.png",
                }
            }
        },
    )
    db.add_all([parent, character, scene])
    db.flush()
    parent.characters.append(character)
    parent.scenes.append(scene)
    db.commit()

    calls = []

    async def fake_generate_reference_image(db_session, prompt, **kwargs):
        calls.append(prompt)
        return f"https://cdn.test/new-live-action-{len(calls)}.png"

    monkeypatch.setattr(style_lock, "generate_reference_image", fake_generate_reference_image)

    missing = await series_router._fill_reference_assets(parent, db)

    assert missing == []
    db.expire_all()
    saved_character = db.query(Character).filter_by(id=character.id).one()
    saved_scene = db.query(Scene).filter_by(id=scene.id).one()
    assert saved_character.avatar_front_url == "https://cdn.test/new-live-action-1.png"
    assert saved_scene.reference_wideshot_url.startswith("https://cdn.test/new-live-action-")
    assert any("photorealistic live-action" in prompt for prompt in calls)


@pytest.mark.asyncio
async def test_style_lock_regenerates_expired_reference_urls(db, monkeypatch):
    from app.routers import series as series_router

    expired = (
        "https://ark-acg-cn-beijing.tos-cn-beijing.volces.com/ref.jpeg"
        "?X-Tos-Date=20000101T000000Z&X-Tos-Expires=86400"
    )
    parent = Series(title="Anchors", logline="Test", genre="drama")
    character = Character(
        name="Lin",
        appearance_desc="short black hair",
        outfit_desc="gray coat",
        avatar_front_url=expired,
        avatar_side_url="https://cdn.test/side.png",
        avatar_threequarter_url="https://cdn.test/threequarter.png",
        avatar_fullbody_url="https://cdn.test/fullbody.png",
    )
    scene = Scene(
        name="Rain Clinic",
        location_desc="neon clinic",
        lighting="cool neon",
        mood="tense",
        reference_wideshot_url=expired,
        reference_midshot_url="https://cdn.test/mid.png",
        reference_aerial_url="https://cdn.test/aerial.png",
    )
    db.add_all([parent, character, scene])
    db.flush()
    parent.characters.append(character)
    parent.scenes.append(scene)

    calls = []

    async def fake_generate_reference_image(db_session, prompt, **kwargs):
        calls.append(prompt)
        return f"https://cdn.test/regenerated-{len(calls)}.png"

    monkeypatch.setattr(style_lock, "generate_reference_image", fake_generate_reference_image)

    missing = await series_router._fill_reference_assets(parent, db)

    assert missing == []
    assert character.avatar_front_url == "https://cdn.test/regenerated-1.png"
    assert character.avatar_side_url == "https://cdn.test/side.png"
    assert scene.reference_wideshot_url == "https://cdn.test/regenerated-2.png"
    assert scene.reference_midshot_url == "https://cdn.test/mid.png"
    assert series_router._character_reference_urls(character)[0] == "https://cdn.test/regenerated-1.png"
    assert series_router._scene_reference_urls(scene)[0] == "https://cdn.test/regenerated-2.png"


@pytest.mark.asyncio
async def test_style_lock_generates_missing_assets_and_records_missing_references(client, db, monkeypatch):
    from app.routers import series as series_router

    series, _ = _create_series(db, with_episode=False)
    generated = [
        json.dumps({
            "characters": [{
                "name": "Lin",
                "role_type": "protagonist",
                "gender": "female",
                "age_range": "28-32",
                "personality": "calm and precise",
                "appearance_desc": "short black hair, sharp eyes, long gray coat",
                "outfit_desc": "gray coat with black boots",
            }]
        }),
        json.dumps({
            "scenes": [{
                "name": "Rain Clinic",
                "scene_type": "indoor",
                "location_desc": "small clinic with neon reflections and rain on glass",
                "lighting": "night",
                "mood": "mysterious",
            }]
        }),
    ]
    monkeypatch.setattr(
        "app.domains.ai_video_series.style_lock.ai_generator.generate_custom",
        AsyncMock(side_effect=generated),
    )
    resp = client.post(f"/api/series/{series.id}/style-lock")

    assert resp.status_code == 200
    assert resp.json()["status"] == "locking"

    data = await series_router._run_style_lock_job(series.id, db=db)
    assert data["story_bible"]["style_lock"]["locked"] is True
    assert data["story_bible"]["style_lock"]["version"] == 1
    assert data["story_bible"]["style_lock"]["agency_trace"]["error_code"] == "EXPERT_MODEL_CONFIG_MISSING"
    agency_team = data["story_bible"]["style_lock"]["agency_team"]
    assert agency_team["version"]
    assert [role["id"] for role in agency_team["core_roles"]] == [
        "story_generator",
        "narrative_designer",
        "visual_storyteller",
        "image_prompt_engineer",
        "prompt_engineer",
        "short_video_editing_coach",
        "douyin_strategist",
    ]
    assert agency_team["quality_gates"]["storyboard"]
    assert data["missing_assets"]

    db.expire_all()
    saved = db.query(Series).filter(Series.id == series.id).one()
    assert saved.story_bible_json["style_lock"]["characters"][0]["name"] == "Lin"
    assert db.query(Character).count() == 1
    assert db.query(Scene).count() == 1
    series_bible_artifact = db.query(AITextArtifact).filter_by(
        series_id=series.id,
        target_type="series",
        target_id=series.id,
        artifact_type="series_bible",
    ).one()
    assert series_bible_artifact.status == "approved"
    assert series_bible_artifact.content_json["style_lock"]["characters"][0]["name"] == "Lin"
    assert series_bible_artifact.review_trace_json["error_code"] == "EXPERT_MODEL_CONFIG_MISSING"

    status = client.get(f"/api/series/{series.id}/style-lock").json()
    assert status["ok"] is True
    assert status["locked"] is True
    assert status["agency_team_status"]["enabled"] is True
    assert status["agency_team_status"]["core_role_count"] == 7
    assert status["reference_status"]["characters"]["total"] == 1
    assert status["reference_status"]["characters"]["ready"] == 0


def test_style_lock_get_reports_locking_status(client, db):
    series, _ = _create_series(db, with_episode=False)
    series.story_bible_json = {
        "style_lock": {
            "locked": False,
            "status": "locking",
            "version": 3,
            "lock_started_at": "2026-06-03T10:00:00+00:00",
        }
    }
    db.commit()

    resp = client.get(f"/api/series/{series.id}/style-lock")

    assert resp.status_code == 200
    data = resp.json()
    assert data["locked"] is False
    assert data["status"] == "locking"
    assert data["version"] == 3


def test_style_lock_get_exposes_reference_progress_for_live_polling(client, db):
    series, _ = _create_series(db, with_episode=False)
    progress = [{
        "asset_type": "character",
        "asset_id": "char-live",
        "slot": "avatar_front_url",
        "status": "ready",
        "url": "/static/image-creation/outputs/live-front.png",
    }]
    series.story_bible_json = {
        "style_lock": {
            "locked": False,
            "status": "locking",
            "version": 3,
            "reference_progress": progress,
        }
    }
    db.commit()

    resp = client.get(f"/api/series/{series.id}/style-lock")

    assert resp.status_code == 200
    assert resp.json()["reference_progress"] == progress


def test_style_lock_post_allows_recovery_from_stale_locking_state(client, db):
    series, _ = _create_series(db, with_episode=False)
    series.story_bible_json = {
        "style_lock": {
            "locked": False,
            "status": "locking",
            "version": 1,
            "lock_started_at": "2026-06-03T10:00:00+00:00",
        }
    }
    db.commit()

    resp = client.post(f"/api/series/{series.id}/style-lock")

    assert resp.status_code == 200
    assert resp.json()["status"] == "locking"
    assert db.query(ProductionJob).filter_by(target_type="series", target_id=series.id, stage="style_lock").count() == 1


def test_style_lock_post_clears_stale_missing_assets_and_progress(client, db):
    series, _ = _create_series(db, with_episode=False)
    series.story_bible_json = {
        "style_lock": {
            "locked": False,
            "status": "blocked",
            "version": 2,
            "missing_assets": [{"slot": "avatar_front_url"}],
            "reference_progress": [{"slot": "avatar_front_url", "status": "failed"}],
            "agency_trace": {"stage_status": "blocked"},
        }
    }
    db.commit()

    resp = client.post(f"/api/series/{series.id}/style-lock")

    assert resp.status_code == 200
    lock = resp.json()["story_bible"]["style_lock"]
    assert lock["status"] == "locking"
    assert lock["version"] == 3
    assert lock["missing_assets"] == []
    assert lock["reference_progress"] == []
    assert "agency_trace" not in lock


def test_style_lock_post_schedules_background_job_without_running_inline(client, db, monkeypatch):
    from app.routers import series as series_router

    series, _ = _create_series(db, with_episode=False)
    resp = client.post(f"/api/series/{series.id}/style-lock")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["status"] == "locking"
    job = db.query(ProductionJob).filter_by(target_type="series", target_id=series.id, stage="style_lock").one()
    assert job.status == "queued"
    assert job.idempotency_key == f"style_lock:{series.id}:v1"
    db.expire_all()
    saved = db.query(Series).filter(Series.id == series.id).one()
    assert saved.story_bible_json["style_lock"]["status"] == "locking"


def test_style_lock_active_job_blocks_duplicate_even_if_story_bible_is_stale(client, db):
    series, _ = _create_series(db, with_episode=False)
    resp = client.post(f"/api/series/{series.id}/style-lock")
    assert resp.status_code == 200
    series.story_bible_json = {"style_lock": {"locked": False, "status": "unlocked", "version": 99}}
    db.commit()

    duplicate = client.post(f"/api/series/{series.id}/style-lock")

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "STYLE_LOCK_IN_PROGRESS"
    assert db.query(ProductionJob).filter_by(target_type="series", target_id=series.id, stage="style_lock").count() == 1


@pytest.mark.asyncio
async def test_style_lock_worker_step_processes_persisted_job(db, monkeypatch):
    from app.routers import series as series_router

    series, _ = _create_series(db, with_episode=False)
    character = Character(name="Lin", role_type="protagonist", avatar_front_url="https://cdn.test/front.png")
    scene = Scene(name="Clinic", reference_wideshot_url="https://cdn.test/wide.png")
    db.add_all([character, scene])
    db.flush()
    series.characters.append(character)
    series.scenes.append(scene)
    db.commit()

    client = TestClient(app)
    resp = client.post(f"/api/series/{series.id}/style-lock")
    assert resp.status_code == 200

    async def fake_generate_reference_image(db_session, prompt, **kwargs):
        return f"https://cdn.test/{len(prompt)}.png"

    monkeypatch.setattr(style_lock, "generate_reference_image", fake_generate_reference_image)
    result = await series_router._run_style_lock_worker_step(db, lease_id="style-worker", batch_size=1)

    assert result["processed"] == 1
    job = db.query(ProductionJob).filter_by(target_type="series", target_id=series.id, stage="style_lock").one()
    assert job.status == "completed"
    saved = db.query(Series).filter(Series.id == series.id).one()
    assert saved.story_bible_json["style_lock"]["status"] == "locked"


@pytest.mark.asyncio
async def test_style_lock_worker_claims_jobs_with_long_lease(db, monkeypatch):
    from app.routers import series as series_router

    claim_kwargs = {}

    def fake_claim_next_job(db_session, **kwargs):
        claim_kwargs.update(kwargs)
        return None

    monkeypatch.setattr(style_lock, "claim_next_job", fake_claim_next_job)

    result = await series_router._run_style_lock_worker_step(db, lease_id="style-worker", batch_size=1)

    assert result["processed"] == 0
    assert claim_kwargs["stage"] == "style_lock"
    assert claim_kwargs["lease_seconds"] == 3600


@pytest.mark.asyncio
async def test_story_plan_worker_step_processes_persisted_job(db, monkeypatch):
    from app.routers import series as series_router

    series, _ = _create_series(db, with_episode=False)
    client = TestClient(app)
    resp = client.post(f"/api/series/{series.id}/story-plan")
    assert resp.status_code == 200
    calls = []

    async def fake_generate_series_story_plan(db_session, series_id, force=False):
        calls.append((db_session, series_id, force))
        return {"series_id": series_id}

    monkeypatch.setattr(story_planning, "generate_series_story_plan", fake_generate_series_story_plan)

    result = await series_router._run_story_plan_worker_step(db, lease_id="story-worker", batch_size=1)

    assert result["processed"] == 1
    assert calls == [(db, series.id, False)]
    job = db.query(ProductionJob).filter_by(target_type="series", target_id=series.id, stage="story_planning").one()
    assert job.status == "completed"
    saved = db.query(Series).filter(Series.id == series.id).one()
    assert saved.story_bible_json["story_planning"]["status"] == "completed"


@pytest.mark.asyncio
async def test_story_plan_worker_claims_jobs_with_long_lease(db, monkeypatch):
    from app.routers import series as series_router

    claim_kwargs = {}

    def fake_claim_next_job(db_session, **kwargs):
        claim_kwargs.update(kwargs)
        return None

    monkeypatch.setattr(story_planning, "claim_next_job", fake_claim_next_job)

    result = await series_router._run_story_plan_worker_step(db, lease_id="story-worker", batch_size=1)

    assert result["processed"] == 0
    assert claim_kwargs["stage"] == "story_planning"
    assert claim_kwargs["lease_seconds"] == 3600


@pytest.mark.asyncio
async def test_style_lock_worker_records_reference_slot_progress(db, monkeypatch):
    from app.routers import series as series_router

    series, _ = _create_series(db, with_episode=False)
    character = Character(
        name="Lin",
        role_type="protagonist",
        appearance_desc="short black hair, sharp eyes",
        outfit_desc="gray coat",
    )
    scene = Scene(
        name="Rain Clinic",
        scene_type="indoor",
        location_desc="small clinic with neon reflections",
        lighting="night",
        mood="mysterious",
    )
    db.add_all([character, scene])
    db.flush()
    series.characters.append(character)
    series.scenes.append(scene)
    series.story_bible_json = {"style_lock": {"status": "locking", "version": 1}}
    db.commit()

    async def fake_generate_reference_image(db_session, prompt, **kwargs):
        if "mid-shot scene lighting" in prompt:
            return None
        return f"https://cdn.test/{len(prompt)}.png"

    monkeypatch.setattr(style_lock, "generate_reference_image", fake_generate_reference_image)

    await series_router._run_style_lock_job(series.id, db=db)

    db.expire_all()
    saved_character = db.query(Character).filter(Character.id == character.id).one()
    saved_scene = db.query(Scene).filter(Scene.id == scene.id).one()
    character_progress = saved_character.meta_json["reference_generation"]
    scene_progress = saved_scene.meta_json["reference_generation"]

    assert character_progress["avatar_front_url"]["status"] == "ready"
    assert character_progress["avatar_front_url"]["source"] == "style_lock"
    assert character_progress["avatar_front_url"]["url"].startswith("https://cdn.test/")
    assert scene_progress["reference_midshot_url"]["status"] == "failed"
    assert scene_progress["reference_midshot_url"]["source"] == "style_lock"
    saved_series = db.query(Series).filter(Series.id == series.id).one()
    progress = saved_series.story_bible_json["style_lock"]["reference_progress"]
    assert any(item["slot"] == "avatar_front_url" and item["status"] == "ready" for item in progress)
    assert any(item["slot"] == "reference_midshot_url" and item["status"] == "failed" for item in progress)


@pytest.mark.asyncio
async def test_style_lock_reference_generation_uses_slot_scoped_idempotency_context(db, monkeypatch):
    from app.routers import series as series_router

    series, _ = _create_series(db, with_episode=False)
    character = Character(name="Lin", role_type="protagonist")
    scene = Scene(name="Clinic", scene_type="indoor")
    db.add_all([character, scene])
    db.flush()
    series.characters.append(character)
    series.scenes.append(scene)
    series.story_bible_json = {"style_lock": {"status": "locking", "version": 7}}
    db.commit()

    contexts = []

    async def fake_generate_reference_url(db_session, prompt, **kwargs):
        contexts.append(kwargs.get("destination_context"))
        return f"https://cdn.test/{len(contexts)}.png"

    monkeypatch.setattr(style_lock, "generate_reference_url", fake_generate_reference_url)

    missing = await series_router._fill_reference_assets(series, db)

    assert missing == []
    character_context = next(item for item in contexts if item["asset_type"] == "character")
    scene_context = next(item for item in contexts if item["asset_type"] == "scene")
    assert character_context == {
        "series_id": series.id,
        "style_lock_version": 7,
        "asset_type": "character",
        "asset_id": character.id,
        "slot": "avatar_front_url",
    }
    assert scene_context == {
        "series_id": series.id,
        "style_lock_version": 7,
        "asset_type": "scene",
        "asset_id": scene.id,
        "slot": "reference_wideshot_url",
    }


@pytest.mark.asyncio
async def test_style_lock_reference_generation_runs_slots_in_parallel(db, monkeypatch):
    from app.routers import series as series_router

    series, _ = _create_series(db, with_episode=False)
    character = Character(name="Lin", role_type="protagonist")
    scene = Scene(name="Clinic", scene_type="indoor")
    db.add_all([character, scene])
    db.flush()
    series.characters.append(character)
    series.scenes.append(scene)
    series.story_bible_json = {"style_lock": {"status": "locking", "version": 1}}
    db.commit()

    in_flight = 0
    max_in_flight = 0

    async def fake_generate_reference_image(db_session, prompt, **kwargs):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return f"https://cdn.test/{kwargs['destination_context']['slot']}.png"

    monkeypatch.setattr(style_lock, "generate_reference_image", fake_generate_reference_image)

    missing = await series_router._fill_reference_assets(series, db)

    assert missing == []
    assert max_in_flight > 1


@pytest.mark.asyncio
async def test_style_lock_blocked_agency_trace_does_not_mark_series_locked(client, db, monkeypatch):
    from app.routers import series as series_router

    series, _ = _create_series(db, with_episode=False)
    character = Character(
        name="Lin",
        role_type="protagonist",
        appearance_desc="short black hair, sharp eyes",
        outfit_desc="gray coat",
        avatar_front_url="https://cdn.test/lin-front.png",
    )
    scene = Scene(
        name="Rain Clinic",
        scene_type="indoor",
        location_desc="small clinic with neon reflections",
        lighting="night",
        mood="mysterious",
        reference_wideshot_url="https://cdn.test/clinic-wide.png",
    )
    db.add_all([character, scene])
    db.flush()
    series.characters.append(character)
    series.scenes.append(scene)
    _expert_review_model(db)
    db.commit()

    async def blocked_style_review(self, *args, **kwargs):
        return {
            "stage": "style_lock",
            "stage_status": "blocked",
            "invocation_ids": ["style-blocked"],
            "invocations": [],
            "summary": "reference anchors are inconsistent",
        }

    monkeypatch.setattr(
        "app.domains.ai_video_series.style_lock.AgencyOrchestrator.run_style_lock_review",
        blocked_style_review,
    )
    resp = client.post(f"/api/series/{series.id}/style-lock")

    assert resp.status_code == 200
    assert resp.json()["status"] == "locking"
    data = await series_router._run_style_lock_job(series.id, db=db)
    assert data["story_bible"]["style_lock"]["locked"] is False
    assert data["story_bible"]["style_lock"]["agency_trace"]["stage_status"] == "blocked"
    db.expire_all()
    saved = db.query(Series).filter(Series.id == series.id).one()
    assert saved.story_bible_json["style_lock"]["locked"] is False
    artifact = db.query(AITextArtifact).filter_by(
        series_id=series.id,
        target_type="series",
        target_id=series.id,
        artifact_type="series_bible",
    ).one()
    assert artifact.status == "review_pending"
    assert artifact.review_trace_json["stage_status"] == "blocked"


@pytest.mark.asyncio
async def test_style_lock_review_timeout_completes_with_partial_trace(client, db, monkeypatch):
    import asyncio
    from app.routers import series as series_router

    series, _ = _create_series(db, with_episode=False)
    character = Character(
        name="Lin",
        role_type="protagonist",
        appearance_desc="short black hair, sharp eyes",
        outfit_desc="gray coat",
        avatar_front_url="https://cdn.test/lin-front.png",
    )
    scene = Scene(
        name="Rain Clinic",
        scene_type="indoor",
        location_desc="small clinic with neon reflections",
        lighting="night",
        mood="mysterious",
        reference_wideshot_url="https://cdn.test/clinic-wide.png",
    )
    db.add_all([character, scene])
    db.flush()
    series.characters.append(character)
    series.scenes.append(scene)
    _expert_review_model(db)
    db.commit()

    async def slow_style_review(self, *args, **kwargs):
        await asyncio.sleep(1)
        return {"stage": "style_lock", "stage_status": "passed"}

    monkeypatch.setattr(style_lock, "STYLE_LOCK_AGENCY_REVIEW_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(
        "app.domains.ai_video_series.style_lock.AgencyOrchestrator.run_style_lock_review",
        slow_style_review,
    )

    data = await series_router._run_style_lock_job(series.id, db=db)

    lock = data["story_bible"]["style_lock"]
    assert lock["status"] == "locked"
    assert lock["locked"] is True
    assert lock["agency_trace"]["stage_status"] == "partial"
    assert lock["agency_trace"]["error_code"] == "STYLE_LOCK_REVIEW_TIMEOUT"
    db.expire_all()
    saved = db.query(Series).filter(Series.id == series.id).one()
    assert saved.story_bible_json["style_lock"]["status"] == "locked"


def test_style_lock_get_replaces_stored_legacy_agency_team(client, db):
    series, _ = _create_series(db, with_episode=False)
    series.story_bible_json = {
        "style_lock": {
            "locked": True,
            "version": 1,
            "agency_team": {
                "enabled": True,
                "version": "legacy-9-role-team",
                "core_roles": [
                    {"id": "short_video_editing_coach"},
                    {"id": "ai_engineer"},
                    {"id": "software_architect"},
                    {"id": "product_manager"},
                ],
                "support_roles": [{"id": "model_qa_specialist"}],
                "quality_gates": {"storyboard": ["legacy gate"]},
            },
        }
    }
    db.commit()

    resp = client.get(f"/api/series/{series.id}/style-lock")

    assert resp.status_code == 200
    data = resp.json()
    team = data["story_bible"]["style_lock"]["agency_team"]
    role_ids = [role["id"] for role in team["core_roles"] + team["support_roles"] + team["quality_roles"]]
    assert role_ids == [
        "story_generator",
        "narrative_designer",
        "visual_storyteller",
        "image_prompt_engineer",
        "prompt_engineer",
        "short_video_editing_coach",
        "douyin_strategist",
        "video_optimization_specialist",
        "style_lock_quality_reviewer",
        "storyboard_quality_reviewer",
        "image_stage_quality_reviewer",
        "image_review_quality_reviewer",
        "video_stage_quality_reviewer",
        "video_review_quality_reviewer",
        "compose_quality_reviewer",
    ]
    assert data["agency_team_status"]["core_role_count"] == 7
    assert data["agency_team_status"]["support_role_count"] == 1
    assert data["agency_team_status"]["quality_role_count"] == 7
    assert not {"ai_engineer", "software_architect", "product_manager", "model_qa_specialist"} & set(role_ids)

    db.expire_all()
    saved = db.query(Series).filter(Series.id == series.id).one()
    saved_team = saved.story_bible_json["style_lock"]["agency_team"]
    saved_role_ids = [role["id"] for role in saved_team["core_roles"] + saved_team["support_roles"] + saved_team["quality_roles"]]
    assert saved_role_ids == role_ids

    series_payload = client.get(f"/api/series/{series.id}").json()["series"]
    series_team = series_payload["story_bible_json"]["style_lock"]["agency_team"]
    series_role_ids = [role["id"] for role in series_team["core_roles"] + series_team["support_roles"] + series_team["quality_roles"]]
    assert series_role_ids == role_ids


def test_director_auto_plan_persists_storyboard_with_references(client, db, monkeypatch):
    from app.services.video_agency_team import build_video_agency_team

    series, episode = _create_series(db)
    character = Character(
        name="Lin",
        role_type="protagonist",
        gender="female",
        appearance_desc="short black hair",
        avatar_front_url="https://cdn.test/lin-front.png",
    )
    scene = Scene(
        name="Rain Clinic",
        scene_type="indoor",
        location_desc="neon clinic",
        reference_wideshot_url="https://cdn.test/clinic-wide.png",
    )
    db.add_all([character, scene])
    db.flush()
    series.characters.append(character)
    series.scenes.append(scene)
    series.story_bible_json = {
        "style_lock": {
            "locked": True,
            "version": 1,
            "visual_style": {"prompt": "cyber-noir, rainy neon, restrained palette"},
            "characters": [{"id": character.id, "name": character.name, "reference_urls": [character.avatar_front_url]}],
            "scenes": [{"id": scene.id, "name": scene.name, "reference_urls": [scene.reference_wideshot_url]}],
            "edit_packaging": {"subtitle_style": "white caption with dark stroke"},
            "agency_team": build_video_agency_team(),
        }
    }
    db.commit()
    generate = AsyncMock(return_value=json.dumps({
        "frames": [{
            "narration": "Lin enters the clinic.",
            "image_prompt": "Lin walks through neon rain into the clinic.",
            "duration": 5,
            "audio_mode": "tts",
        }]
        }))
    monkeypatch.setattr("app.routers.director.ai_generator.generate_custom", generate)

    resp = client.post("/api/director/auto-plan", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration": 30,
    })

    assert resp.status_code == 200
    data = resp.json()
    frame = data["storyboard"]["frames"][0]
    assert frame["character_ids"] == [character.id]
    assert frame["scene_id"] == scene.id
    assert "https://cdn.test/lin-front.png" in frame["reference_urls"]
    assert "https://cdn.test/clinic-wide.png" in frame["reference_urls"]
    assert frame["continuity_notes"]
    assert data["storyboard"]["agency_team_version"]
    assert data["storyboard"]["agency_trace"]["error_code"] == "EXPERT_MODEL_CONFIG_MISSING"
    assert data["storyboard"]["quality_gates"]["storyboard"]
    assert "douyin_strategist" in generate.call_args.args[2]
    assert "short_video_editing_coach" in generate.call_args.args[2]

    db.expire_all()
    saved_episode = db.query(Episode).filter(Episode.id == episode.id).one()
    assert saved_episode.storyboard_json["frames"][0]["reference_urls"] == frame["reference_urls"]
    assert saved_episode.storyboard_json["agency_trace"]["error_code"] == "EXPERT_MODEL_CONFIG_MISSING"


def test_auto_plan_blocked_agency_trace_does_not_persist_storyboard(client, db, monkeypatch):
    from app.services.video_agency_team import build_video_agency_team

    series, episode = _create_series(db)
    _expert_review_model(db)
    character = Character(
        name="Lin",
        appearance_desc="short black hair",
        outfit_desc="gray coat",
        avatar_front_url="https://cdn.test/lin-front.png",
    )
    scene = Scene(
        name="Rain Clinic",
        location_desc="neon clinic",
        reference_wideshot_url="https://cdn.test/clinic-wide.png",
    )
    db.add_all([character, scene])
    db.flush()
    series.characters.append(character)
    series.scenes.append(scene)
    series.story_bible_json = {
        "style_lock": {
            "locked": True,
            "version": 1,
            "visual_style": {"prompt": "cyber-noir"},
            "characters": [{"id": character.id, "name": character.name, "reference_urls": [character.avatar_front_url]}],
            "scenes": [{"id": scene.id, "name": scene.name, "reference_urls": [scene.reference_wideshot_url]}],
            "agency_team": build_video_agency_team(),
        }
    }
    db.commit()

    monkeypatch.setattr(
        "app.routers.director.ai_generator.generate_custom",
        AsyncMock(return_value=json.dumps({
            "frames": [{
                "narration": "Lin enters the clinic.",
                "image_prompt": "Lin walks through neon rain into the clinic.",
                "duration": 5,
            }]
        })),
    )

    async def blocked_storyboard_review(self, *args, **kwargs):
        return {
            "stage": "storyboard",
            "stage_status": "blocked",
            "invocation_ids": ["storyboard-blocked"],
            "invocations": [],
            "summary": "storyboard does not preserve continuity",
        }

    monkeypatch.setattr(
        "app.routers.director.AgencyOrchestrator.run_storyboard_review",
        blocked_storyboard_review,
    )

    resp = client.post("/api/director/auto-plan", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration": 30,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["agency_trace"]["stage_status"] == "blocked"
    db.expire_all()
    saved_episode = db.query(Episode).filter(Episode.id == episode.id).one()
    assert saved_episode.storyboard_json in ({}, None)


def test_director_auto_plan_generation_timeout_persists_fallback_storyboard(client, db, monkeypatch):
    from app.services.video_agency_team import build_video_agency_team

    series, episode = _create_series(db)
    character = Character(
        name="Lin",
        appearance_desc="short black hair",
        outfit_desc="gray coat",
        avatar_front_url="https://cdn.test/lin-front.png",
    )
    scene = Scene(
        name="Rain Clinic",
        location_desc="neon clinic",
        reference_wideshot_url="https://cdn.test/clinic-wide.png",
    )
    db.add_all([character, scene])
    db.flush()
    series.characters.append(character)
    series.scenes.append(scene)
    series.story_bible_json = {
        "style_lock": {
            "locked": True,
            "version": 1,
            "visual_style": {"prompt": "realistic clinic documentary"},
            "characters": [{"id": character.id, "name": character.name, "reference_urls": [character.avatar_front_url]}],
            "scenes": [{"id": scene.id, "name": scene.name, "reference_urls": [scene.reference_wideshot_url]}],
            "agency_team": build_video_agency_team(),
        }
    }
    db.commit()

    async def slow_generate(*args, **kwargs):
        import asyncio

        await asyncio.sleep(1)
        return json.dumps({"frames": []})

    monkeypatch.setattr("app.routers.director.DIRECTOR_GENERATION_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr("app.routers.director.ai_generator.generate_custom", slow_generate)

    resp = client.post("/api/director/auto-plan", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration": 30,
    })

    assert resp.status_code == 200
    storyboard = resp.json()["storyboard"]
    assert storyboard["generation_trace"]["error_code"] == "DIRECTOR_GENERATION_TIMEOUT"
    assert storyboard["frames"]
    assert storyboard["frames"][0]["reference_urls"]

    db.expire_all()
    saved_episode = db.query(Episode).filter(Episode.id == episode.id).one()
    assert saved_episode.storyboard_json["generation_trace"]["error_code"] == "DIRECTOR_GENERATION_TIMEOUT"


def test_director_auto_plan_review_timeout_persists_partial_trace(client, db, monkeypatch):
    from app.services.video_agency_team import build_video_agency_team

    series, episode = _create_series(db)
    _expert_review_model(db)
    character = Character(
        name="Lin",
        appearance_desc="short black hair",
        outfit_desc="gray coat",
        avatar_front_url="https://cdn.test/lin-front.png",
    )
    scene = Scene(
        name="Rain Clinic",
        location_desc="neon clinic",
        reference_wideshot_url="https://cdn.test/clinic-wide.png",
    )
    db.add_all([character, scene])
    db.flush()
    series.characters.append(character)
    series.scenes.append(scene)
    series.story_bible_json = {
        "style_lock": {
            "locked": True,
            "version": 1,
            "visual_style": {"prompt": "realistic clinic documentary"},
            "characters": [{"id": character.id, "name": character.name, "reference_urls": [character.avatar_front_url]}],
            "scenes": [{"id": scene.id, "name": scene.name, "reference_urls": [scene.reference_wideshot_url]}],
            "agency_team": build_video_agency_team(),
        }
    }
    db.commit()

    monkeypatch.setattr(
        "app.routers.director.ai_generator.generate_custom",
        AsyncMock(return_value=json.dumps({"frames": [{
            "narration": "Lin enters the clinic.",
            "image_prompt": "Lin walks through the clinic.",
            "duration": 5,
        }]})),
    )

    async def slow_storyboard_review(self, *args, **kwargs):
        import asyncio

        await asyncio.sleep(1)
        return {"stage": "storyboard", "stage_status": "passed"}

    monkeypatch.setattr("app.routers.director.DIRECTOR_AGENCY_REVIEW_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(
        "app.routers.director.AgencyOrchestrator.run_storyboard_review",
        slow_storyboard_review,
    )

    resp = client.post("/api/director/auto-plan", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration": 30,
    })

    assert resp.status_code == 200
    storyboard = resp.json()["storyboard"]
    assert storyboard["agency_trace"]["stage_status"] == "partial"
    assert storyboard["agency_trace"]["error_code"] == "DIRECTOR_REVIEW_TIMEOUT"

    db.expire_all()
    saved_episode = db.query(Episode).filter(Episode.id == episode.id).one()
    assert saved_episode.storyboard_json["agency_trace"]["error_code"] == "DIRECTOR_REVIEW_TIMEOUT"


@pytest.mark.asyncio
async def test_pipeline_uses_saved_storyboard_and_persists_episode_and_video(db, test_db, monkeypatch):
    from app.routers import pipeline
    from app.services.video_agency_team import build_video_agency_team

    TestSession = sessionmaker(bind=test_db, autocommit=False, autoflush=False)
    monkeypatch.setattr(pipeline, "SessionLocal", TestSession)
    monkeypatch.setattr("app.services.agency_runtime.AgencySkillRuntime.invoke", _agency_pass)

    series, episode = _create_series(db)
    _expert_review_model(db)
    series.story_bible_json = {
        "style_lock": {
            "locked": True,
            "version": 1,
            "agency_team": build_video_agency_team(),
            "visual_style": {"prompt": "cyber-noir, rainy neon, restrained palette"},
            "edit_packaging": {"subtitle_style": "white caption with dark stroke"},
            "audio_packaging": {"bgm_policy": "keep a restrained BGM bed"},
        }
    }
    episode.storyboard_json = {
        "frames": [{
            "narration": "Lin studies the room.",
            "image_prompt": "consistent cyber-noir clinic interior",
            "duration": 5,
            "audio_mode": "tts",
            "character_ids": ["char-1"],
            "scene_id": "scene-1",
            "reference_urls": ["https://cdn.test/ref.png"],
            "continuity_notes": "Keep Lin in gray coat.",
        }]
    }
    run = PipelineRun(series_id=series.id, episode_id=episode.id, mode="fully_automatic", status="running")
    db.add(run)
    db.commit()

    captured_payloads = []

    async def fake_pixelle_request(method, path, db=None, **kwargs):
        captured_payloads.append((path, kwargs.get("json") or {}))
        if path == "/api/image/generate":
            return {"images": ["https://cdn.test/generated-frame.png"]}
        if path == "/api/content/narration":
            return {"narration": "Lin studies the room."}
        if path == "/api/content/title":
            return {"title": "Pilot"}
        if path == "/api/content/image-prompt":
            return {"image_prompt": "consistent cyber-noir clinic interior"}
        if path == "/api/video/generate/async":
            return {"task_id": "pixelle-task-1"}
        if path == "/api/video/task/pixelle-task-1":
            return {"status": "completed", "progress": 100, "video_path": "frame-1.mp4", "duration": 5}
        if path == "/api/postproduction/execute":
            return {"video_path": "server/data/videos/final.mp4", "duration": 5}
        raise AssertionError(f"Unexpected Pixelle path: {path}")

    monkeypatch.setattr(pipeline, "_pixelle_request", fake_pixelle_request)
    monkeypatch.setattr(pipeline.asyncio, "sleep", AsyncMock())

    await pipeline._run_all_layers(run.id)

    db.expire_all()
    saved_run = db.query(PipelineRun).filter(PipelineRun.id == run.id).one()
    postproduction_payload = [payload for path, payload in captured_payloads if path == "/api/postproduction/execute"][0]
    render_payloads = [payload for path, payload in captured_payloads if path == "/api/video/generate/async"]

    assert saved_run.status == "completed"
    assert saved_run.layers_json["0"]["agency_trace_status"] == "legacy_summary"
    assert saved_run.layers_json["1"]["agency_trace_status"] == "complete"
    assert len(render_payloads) >= 1
    assert len(captured_payloads) >= 6  # 6 layers completed
