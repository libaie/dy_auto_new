from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app.db.models import (
    AITextArtifact,
    AITextArtifactConsumer,
    ProductionAuditEvent,
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    VideoProductionRun,
    Character,
    Series,
    Episode,
    Scene,
)
from app.main import app
from app.domains.ai_video_series.asset_director_service import AssetDirectorError
from app.domains.video_production.video_production_run_types import MOCK_SERIES_SCALE, REAL_SHORT_E2E


@pytest.fixture(autouse=True)
def stub_series_story_plan_for_start_flow(monkeypatch):
    async def fake_generate_series_story_plan(db_session, series_id, force=False):
        from app.db.models import AITextArtifact, Episode
        from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

        service = AITextArtifactService(db_session)
        series = db_session.query(Series).filter_by(id=series_id).one()
        episodes = (
            db_session.query(Episode)
            .filter(Episode.series_id == series_id)
            .order_by(Episode.episode_number)
            .all()
        )
        specs = [
            (
                "series_story_plan",
                {
                    "schema_version": "series.story_plan.v1",
                    "season_question": "Can she keep the clinic alive?",
                    "season_promise": series.logline or series.title,
                },
                "Can she keep the clinic alive?",
            ),
            (
                "season_arc",
                {
                    "schema_version": "series.season_arc.v1",
                    "arc_summary": "Clinic pressure escalates each episode.",
                },
                "Clinic pressure escalates each episode.",
            ),
        ]
        for artifact_type, content_json, content_text in specs:
            if service.latest_approved(target_type="series", target_id=series_id, artifact_type=artifact_type):
                continue
            artifact = service.create_artifact(
                series_id=series_id,
                target_type="series",
                target_id=series_id,
                artifact_type=artifact_type,
                source_type="ai",
                content_json=content_json,
                content_text=content_text,
                model_trace_json={
                    "stage": "story_planning",
                    "stage_status": "expert",
                    "expert_id": "story_generator",
                    "source": "test_stub",
                },
            )
            service.approve_artifact(artifact.id)

        for episode in episodes:
            latest = service.latest_approved(
                target_type="episode",
                target_id=episode.id,
                artifact_type="episode_outline",
            )
            if latest and latest.source_type == "human_edit":
                continue
            if latest and latest.source_type != "system_backfill":
                continue
            artifact = service.create_artifact(
                series_id=series_id,
                episode_id=episode.id,
                target_type="episode",
                target_id=episode.id,
                artifact_type="episode_outline",
                source_type="ai",
                parent_artifact_id=latest.id if latest else None,
                content_json={
                    "schema_version": "series.episode_outline.v1",
                    "episode_number": int(episode.episode_number),
                    "title": episode.title or f"Episode {episode.episode_number}",
                    "hook": "Clinic opens with a crisis.",
                    "episode_goal": "Expose the breakfast mistake.",
                    "central_conflict": series.logline or series.title,
                    "reversal": "The trusted advice is wrong.",
                    "cliffhanger": "A new patient arrives.",
                    "previous_episode_handoff": "",
                    "next_episode_handoff": "A new patient arrives.",
                    "character_state_changes": [],
                    "foreshadowing_introduced": ["A new patient arrives."],
                    "foreshadowing_resolved": [],
                    "character_ids": ["char-1"],
                    "scene_ids": ["scene-1"],
                    "asset_usage": {
                        "characters": [
                            {
                                "id": "char-1",
                                "name": "老李",
                                "usage": "本集控糖建议的行动者。",
                                "source": "existing",
                            }
                        ],
                        "scenes": [
                            {
                                "id": "scene-1",
                                "name": "社区公园",
                                "usage": "本集健康建议的现实场景。",
                                "source": "existing",
                            }
                        ],
                    },
                },
                content_text="Clinic opens with a crisis.",
                model_trace_json={
                    "stage": "story_planning",
                    "stage_status": "expert",
                    "expert_id": "story_generator",
                    "source": "test_stub",
                },
            )
            service.approve_artifact(artifact.id)

        return {
            "ok": True,
            "artifacts": db_session.query(AITextArtifact).filter_by(series_id=series_id).count(),
        }

    monkeypatch.setattr("app.domains.video_production.production_run_service.generate_series_story_plan", fake_generate_series_story_plan)

    async def fake_asset_director(db_arg, series_id, episode_id):
        return {"status": "ready", "artifact": None, "readiness": {"status": "ready"}}

    monkeypatch.setattr(
        "app.domains.video_production.production_run_service.ensure_asset_director_plan_for_episode",
        fake_asset_director,
    )
    monkeypatch.setattr(
        "app.domains.video_production.video_production_service.ensure_asset_director_plan_for_episode",
        fake_asset_director,
        raising=False,
    )


def _series_episode(db, *, locked=True, storyboard=True):
    series = Series(
        title="Start Flow",
        logline="One sentence",
        genre="drama",
        target_duration=10,
        story_bible_json={
            "style_lock": {
                "locked": locked,
                "version": 1,
                "visual_style": {"prompt": "realistic documentary"},
                "characters": [{
                    "id": "char-1",
                    "name": "老李",
                    "reference_urls": ["/static/characters/laoli-front.png"],
                }],
                "scenes": [{
                    "id": "scene-1",
                    "name": "社区公园",
                    "reference_urls": ["/static/scenes/park.png"],
                }],
            }
        },
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={
            "frames": [{
                "frame_id": "shot-1",
                "scene_id": "scene-1",
                "character_ids": ["char-1"],
                "duration": 10,
                "image_prompt": "A",
                "video_prompt": "B",
                "reference_urls": ["/static/characters/laoli-front.png", "/static/scenes/park.png"],
            }]
        } if storyboard else {"frames": []},
    )
    db.add(episode)
    db.commit()
    return series, episode


def test_start_flow_requires_asset_director_before_run_creation(db, monkeypatch):
    calls = []
    run_counts_at_call = []

    async def fake_director(db_arg, series_id, episode_id):
        calls.append((series_id, episode_id))
        run_counts_at_call.append(db_arg.query(VideoProductionRun).count())
        return {"status": "ready", "artifact": None, "readiness": {"status": "ready"}}

    monkeypatch.setattr(
        "app.domains.video_production.production_run_service.ensure_asset_director_plan_for_episode",
        fake_director,
    )
    series, episode = _series_episode(db)
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    assert calls == [(series.id, episode.id)]
    assert run_counts_at_call == [0]


@pytest.mark.parametrize(
    "code",
    [
        "ASSET_DIRECTOR_INPUTS_MISSING",
        "ASSET_DIRECTOR_PLAN_STALE",
        "ASSET_DIRECTOR_REFERENCES_MISSING",
        "ASSET_DIRECTOR_REFERENCES_FAILED",
    ],
)
def test_start_flow_blocks_on_asset_director_error(db, monkeypatch, code):
    async def fake_director(db_arg, series_id, episode_id):
        raise AssetDirectorError(code=code, message=f"{code} message", details={"code": code})

    monkeypatch.setattr(
        "app.domains.video_production.production_run_service.ensure_asset_director_plan_for_episode",
        fake_director,
    )
    series, episode = _series_episode(db)
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": False,
    })

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["error_code"] == "EPISODE_ASSET_SCOPE_MISSING"
    assert detail["message"] == f"{code} message"
    assert detail["cause"] == code
    assert detail["repair_action"] == {
        "ASSET_DIRECTOR_INPUTS_MISSING": "Open AI text artifacts, generate the missing scripts/storyboards or asset director plan, then retry production.",
        "ASSET_DIRECTOR_PLAN_STALE": "Regenerate the asset director plan from the latest scripts, storyboards, and style lock, then retry production.",
        "ASSET_DIRECTOR_REFERENCES_MISSING": "Generate missing character and scene reference images, then retry production.",
        "ASSET_DIRECTOR_REFERENCES_FAILED": "Fix failed reference image generation in the AI text artifact or asset workflow, then retry production.",
    }[code]
    assert detail["repair_route"] == f"/series/{series.id}/ai-text-artifacts"
    assert detail["retryable"] is True
    assert detail["affected_ids"] == [episode.id]
    assert db.query(VideoProductionRun).count() == 0


@pytest.mark.parametrize(
    ("status", "expected_cause"),
    [
        ("needs_reference", "ASSET_DIRECTOR_REFERENCES_MISSING"),
        ("reference_failed", "ASSET_DIRECTOR_REFERENCES_FAILED"),
    ],
)
def test_start_flow_blocks_on_asset_director_non_ready_return(db, monkeypatch, status, expected_cause):
    async def fake_director(db_arg, series_id, episode_id):
        return {"status": status, "artifact": None, "readiness": {"status": status}}

    monkeypatch.setattr(
        "app.domains.video_production.production_run_service.ensure_asset_director_plan_for_episode",
        fake_director,
    )
    series, episode = _series_episode(db)
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": False,
    })

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["error_code"] == "EPISODE_ASSET_SCOPE_MISSING"
    assert detail["cause"] == expected_cause
    assert detail["repair_route"] == f"/series/{series.id}/ai-text-artifacts"
    assert detail["retryable"] is True
    assert detail["affected_ids"] == [episode.id]
    assert db.query(VideoProductionRun).count() == 0
    assert db.query(ProductionPlan).count() == 0


def test_legacy_start_images_blocks_on_asset_director_non_ready_return(db, monkeypatch):
    async def fake_director(db_arg, series_id, episode_id):
        return {"status": "stale", "artifact": None, "readiness": {"status": "stale"}}

    monkeypatch.setattr(
        "app.domains.video_production.video_production_service.ensure_asset_director_plan_for_episode",
        fake_director,
        raising=False,
    )
    series, episode = _series_episode(db)
    client = TestClient(app)

    create_resp = client.post("/api/video-production/runs", json={
        "series_id": series.id,
        "episode_id": episode.id,
    })
    assert create_resp.status_code == 200
    run_id = create_resp.json()["run"]["id"]

    resp = client.post(f"/api/video-production/runs/{run_id}/start-images")

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["error_code"] == "EPISODE_ASSET_SCOPE_MISSING"
    assert detail["cause"] == "ASSET_DIRECTOR_PLAN_STALE"
    assert detail["repair_route"] == f"/series/{series.id}/ai-text-artifacts"
    assert detail["retryable"] is True
    assert detail["affected_ids"] == [episode.id]

@pytest.mark.parametrize(
    ("director_result", "expected_cause"),
    [
        (
            AssetDirectorError(
                code="ASSET_DIRECTOR_PLAN_STALE",
                message="Asset director plan input fingerprint is stale.",
                details={"status": "stale"},
            ),
            "ASSET_DIRECTOR_PLAN_STALE",
        ),
        ({"status": "stale", "artifact": None, "readiness": {"status": "stale"}}, "ASSET_DIRECTOR_PLAN_STALE"),
    ],
)
def test_linked_start_images_blocks_on_asset_director_gate(db, monkeypatch, director_result, expected_cause):
    async def fake_director(db_arg, series_id, episode_id):
        if isinstance(director_result, AssetDirectorError):
            raise director_result
        return director_result

    monkeypatch.setattr(
        "app.domains.video_production.video_production_service.ensure_asset_director_plan_for_episode",
        fake_director,
        raising=False,
    )
    series, episode = _series_episode(db)
    plan = ProductionPlan(series_id=series.id, status="ready", active_version=1, budget_limit=1)
    db.add(plan)
    db.flush()
    production_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id, order_index=1, status="ready")
    db.add(production_episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        production_link_status="linked",
        status="storyboard_ready",
        current_stage="storyboard_ready",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.commit()
    client = TestClient(app)

    resp = client.post(f"/api/video-production/runs/{run.id}/start-images")

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["error_code"] == "EPISODE_ASSET_SCOPE_MISSING"
    assert detail["cause"] == expected_cause
    assert detail["repair_route"] == f"/series/{series.id}/ai-text-artifacts"
    assert detail["retryable"] is True
    assert detail["affected_ids"] == [episode.id]

def test_start_flow_auto_generates_missing_storyboard_before_creating_run(db, monkeypatch):
    series, episode = _series_episode(db, storyboard=False)
    client = TestClient(app)

    async def fake_generate_custom(*args, **kwargs):
        return """
        {"frames":[{"frame_id":"shot-1","scene_id":"scene-1","character_ids":["char-1"],"duration":10,
        "image_prompt":"老李在社区公园讲控糖经验","narration":"控糖第一步，先看早餐。","audio_mode":"tts",
        "continuity_notes":"保持真实纪录片质感。"}]}
        """

    monkeypatch.setattr("app.domains.model_configuration.ai_generator.ai_generator.generate_custom", fake_generate_custom)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    db.refresh(episode)
    assert episode.storyboard_json["frames"][0]["reference_urls"]
    assert [frame["time_range"] for frame in episode.storyboard_json["frames"]] == [
        "0-2秒",
        "2-4秒",
        "4-6秒",
        "6-8秒",
        "8-10秒",
    ]
    assert episode.storyboard_json["frames"][1]["start_second"] == 2.0
    assert episode.storyboard_json["frames"][1]["end_second"] == 4.0
    frame = episode.storyboard_json["frames"][1]
    assert "时间段: 2-4秒" in frame["image_prompt"]
    assert "主体/角色:" in frame["image_prompt"]
    assert "场景/环境:" in frame["image_prompt"]
    assert "画面动作:" in frame["image_prompt"]
    assert "秒段细节: 2-4秒:" in frame["image_prompt"]
    assert "视线" in frame["image_prompt"]
    assert "眉眼" in frame["image_prompt"]
    assert "嘴角/唇部" in frame["image_prompt"]
    assert "头部" in frame["image_prompt"]
    assert "手部/身体" in frame["image_prompt"]
    assert "镜头语言:" in frame["video_prompt"]
    assert "情绪/节奏:" in frame["video_prompt"]
    assert "连续性:" in frame["video_prompt"]
    assert "秒段细节: 2-4秒:" in frame["video_prompt"]
    assert "情绪由紧张" in frame["video_prompt"]
    assert "无黑屏、无转场" in frame["video_prompt"]
    assert resp.json()["run"]["production_link_status"] == "linked"
    assert db.query(ProductionSegment).count() == 5


def test_start_flow_story_artifacts_use_story_generator_trace(db):
    series, episode = _series_episode(db, storyboard=True)
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    artifact = db.query(AITextArtifact).filter_by(
        series_id=series.id,
        artifact_type="series_story_plan",
        status="approved",
    ).one()
    assert artifact.model_trace_json["stage"] == "story_planning"
    assert artifact.model_trace_json["expert_id"] == "story_generator"


def test_start_flow_prefers_script_pipeline_storyboard_when_missing(db, monkeypatch):
    series, episode = _series_episode(db, storyboard=False)
    client = TestClient(app)
    captured = {}

    class FakePipelineManager:
        async def start_or_resume(
            self,
            db_session,
            *,
            series_id,
            episode_id,
            source_prompt,
            tags,
            target_duration_seconds,
            episode_asset_scope=None,
        ):
            captured["source_prompt"] = source_prompt
            captured["episode_asset_scope"] = episode_asset_scope
            target = db_session.query(Episode).filter_by(id=episode_id, series_id=series_id).one()
            target.storyboard_json = {
                "source": "dramatic_script_pipeline",
                "frames": [
                    {
                        "frame_id": "script-shot-001",
                        "duration": 2,
                        "narration": "震惊！老李发现早餐问题。",
                        "image_prompt": "老李看向桌上的早餐。",
                        "video_prompt": "镜头推近早餐细节。",
                    },
                    {
                        "frame_id": "script-shot-002",
                        "duration": 2,
                        "narration": "紧张！他开始调整选择。",
                        "image_prompt": "老李拿起新的食物搭配。",
                        "video_prompt": "手部动作快速切换。",
                    },
                ],
            }
            db_session.flush()

    monkeypatch.setattr("app.domains.video_production.production_run_service.PipelineManager", FakePipelineManager)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 4,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    db.refresh(episode)
    frames = episode.storyboard_json["frames"]
    assert [frame["frame_id"] for frame in frames] == ["script-shot-001", "script-shot-002"]
    assert [frame["time_range"] for frame in frames] == ["0-2秒", "2-4秒"]
    assert frames[0]["reference_urls"]
    assert "整季故事规划" in captured["source_prompt"]
    assert "Can she keep the clinic alive?" in captured["source_prompt"]
    assert "本集故事卡" in captured["source_prompt"]
    assert "Clinic opens with a crisis." in captured["source_prompt"]
    assert "本集资产清单" in captured["source_prompt"]
    assert captured["source_prompt"].index("本集资产清单") < captured["source_prompt"].index("已批准的系列故事上下文")
    assert "老李" in captured["source_prompt"]
    assert "社区公园" in captured["source_prompt"]
    assert captured["episode_asset_scope"]["character_ids"] == ["char-1"]
    assert captured["episode_asset_scope"]["scene_ids"] == ["scene-1"]
    assert db.query(ProductionSegment).count() == 2


def test_start_flow_blocks_script_generation_with_blocked_expert_gate(db, monkeypatch):
    series, episode = _series_episode(db, storyboard=False)
    client = TestClient(app)

    class FakePipelineManager:
        async def start_or_resume(
            self,
            db_session,
            *,
            series_id,
            episode_id,
            source_prompt,
            tags,
            target_duration_seconds,
            episode_asset_scope=None,
        ):
            target = db_session.query(Episode).filter_by(id=episode_id, series_id=series_id).one()
            target.script_json = {
                "source": "dramatic_script_pipeline",
                "agency_trace": {"visual_shots": {"stage_status": "blocked"}},
            }
            target.storyboard_json = {
                "source": "dramatic_script_pipeline",
                "frames": [{
                    "frame_id": "blocked-shot",
                    "scene_id": "scene-1",
                    "character_ids": ["char-1"],
                    "duration": 2,
                    "image_prompt": "blocked image",
                    "video_prompt": "blocked video",
                }],
            }
            db_session.flush()
            return SimpleNamespace(agency_trace={"visual_shots": {"stage_status": "blocked"}})

    monkeypatch.setattr("app.domains.video_production.production_run_service.PipelineManager", FakePipelineManager)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 2,
        "autostart_images": False,
    })

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["error_code"] == "REVIEW_GATE_BLOCKED"
    assert detail["cause"] == "script_generation_gate_blocked"
    assert db.query(VideoProductionRun).count() == 0

def test_start_flow_blocks_existing_script_snapshot_with_blocked_expert_gate(db):
    series, episode = _series_episode(db, storyboard=True)
    episode.script_json = {
        "source": "dramatic_script_pipeline",
        "agency_trace": {"visual_shots": {"stage_status": "failed"}},
    }
    db.commit()
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 2,
        "autostart_images": False,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["cause"] == "script_generation_gate_blocked"
    assert db.query(VideoProductionRun).count() == 0


def test_start_flow_blocks_approved_script_artifact_with_blocked_expert_gate(db):
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

    series, episode = _series_episode(db, storyboard=True)
    service = AITextArtifactService(db)
    artifact = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_script",
        source_type="ai",
        content_json={"source": "dramatic_script_pipeline"},
        review_trace_json={"visual_shots": {"stage_status": "blocked"}},
    )
    service.approve_artifact(artifact.id)
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 2,
        "autostart_images": False,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["cause"] == "script_generation_gate_blocked"
    assert db.query(VideoProductionRun).count() == 0

def test_start_flow_generates_missing_episode_script_even_when_storyboard_exists(db, monkeypatch):
    series, episode = _series_episode(db, storyboard=True)
    client = TestClient(app)
    captured = {"called": False}

    class FakePipelineManager:
        async def start_or_resume(
            self,
            db_session,
            *,
            series_id,
            episode_id,
            source_prompt,
            tags,
            target_duration_seconds,
            episode_asset_scope=None,
        ):
            captured["called"] = True
            target = db_session.query(Episode).filter_by(id=episode_id, series_id=series_id).one()
            target.script_json = {
                "source": "dramatic_script_pipeline",
                "scenes": [{"summary": "generated script scene"}],
            }
            db_session.flush()

    monkeypatch.setattr("app.domains.video_production.production_run_service.PipelineManager", FakePipelineManager)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    assert captured["called"] is True
    db.refresh(episode)
    assert episode.script_json["scenes"][0]["summary"] == "generated script scene"
    artifact = db.query(AITextArtifact).filter_by(
        series_id=series.id,
        episode_id=episode.id,
        artifact_type="episode_script",
        status="approved",
    ).one()
    assert artifact.content_json["scenes"][0]["summary"] == "generated script scene"


def test_start_flow_rebuilds_real_short_storyboard_when_references_are_missing(db):
    series, episode = _series_episode(db, storyboard=True)
    episode.storyboard_json = {
        "frames": [{
            "frame_id": "shot-1",
            "duration": 10,
            "image_prompt": "Plain shot without locked references",
            "video_prompt": "Slow pan",
        }]
    }
    db.commit()
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "budget_limit": 1,
        "autostart_images": False,
        "run_type": "real_short_e2e",
    })

    assert resp.status_code == 200
    db.refresh(episode)
    frame = episode.storyboard_json["frames"][0]
    assert frame["scene_id"] == "scene-1"
    assert frame["character_ids"] == ["char-1"]
    assert frame["reference_urls"]
    assert db.query(ProductionSegment).count() == 2
    assert all(segment.reference_roles_json for segment in db.query(ProductionSegment).all())


def test_start_flow_creates_plan_segments_linked_run_and_returns_route(db):
    series, episode = _series_episode(db)
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["route"] == f"/video-production/{body['run']['id']}"
    assert body["run"]["production_link_status"] == "linked"
    assert db.query(ProductionSegment).count() == 2

    run = db.query(VideoProductionRun).filter_by(id=body["run"]["id"]).one()
    assert run.production_plan_id
    assert run.production_episode_id
    assert run.model_trace_json["autopilot"] == {"enabled": False, "source": "episode_start"}
    assert db.query(ProductionAuditEvent).filter_by(run_id=run.id, event_type="run.created").count() == 1
    db.refresh(episode)
    assert episode.status == "rendering"


def test_start_flow_blocks_when_episode_asset_scope_is_missing(db):
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

    series, episode = _series_episode(db)
    series.story_bible_json = {"style_lock": {"locked": True, "version": 1, "visual_style": {}}}
    episode.storyboard_json = {
        "frames": [{
            "frame_id": "shot-missing-assets",
            "duration": 2,
            "image_prompt": "A",
            "video_prompt": "B",
        }]
    }
    service = AITextArtifactService(db)
    manual = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
        source_type="human_edit",
        content_json={"episode_number": 1, "episode_goal": "Missing assets"},
        content_text="Missing assets",
    )
    service.approve_artifact(manual.id)
    db.commit()
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 2,
        "autostart_images": False,
    })

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["error_code"] == "EPISODE_ASSET_SCOPE_MISSING"
    assert detail["affected_ids"] == [episode.id]


def test_start_flow_blocks_style_lock_fallback_when_episode_scope_is_missing(db):
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

    series, episode = _series_episode(db, storyboard=False)
    service = AITextArtifactService(db)
    manual = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
        source_type="human_edit",
        content_json={"episode_number": 1, "episode_goal": "No scoped assets"},
        content_text="No scoped assets",
    )
    service.approve_artifact(manual.id)
    db.commit()
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": False,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "EPISODE_ASSET_SCOPE_MISSING"


def test_start_flow_blocks_unlinked_episode_asset_ids(db):
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

    series, episode = _series_episode(db)
    series.story_bible_json = {"style_lock": {"locked": True, "version": 1, "visual_style": {}}}
    unlinked_character = Character(name="Unlinked", role_type="supporting", gender="female")
    scene = Scene(name="Linked Room", scene_type="indoor")
    series.scenes.append(scene)
    episode.storyboard_json = {
        "frames": [{
            "frame_id": "shot-stale-scope",
            "duration": 2,
            "image_prompt": "A",
            "video_prompt": "B",
        }]
    }
    db.add(unlinked_character)
    db.flush()
    service = AITextArtifactService(db)
    manual = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
        source_type="human_edit",
        content_json={
            "episode_number": 1,
            "episode_goal": "Stale character",
            "character_ids": [unlinked_character.id],
            "scene_ids": [scene.id],
        },
        content_text="Stale character",
    )
    service.approve_artifact(manual.id)
    db.commit()
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 2,
        "autostart_images": False,
    })

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["error_code"] == "EPISODE_ASSET_SCOPE_MISSING"
    assert detail["cause"] == "invalid_episode_asset_scope"


def test_start_flow_applies_episode_asset_scope_to_storyboard_frames(db):
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

    series, episode = _series_episode(db)
    series.story_bible_json = {"style_lock": {"locked": True, "version": 1, "visual_style": {}}}
    character = Character(name="Scope Lead", role_type="protagonist", gender="female")
    scene = Scene(name="Scope Room", scene_type="indoor")
    series.characters.append(character)
    series.scenes.append(scene)
    episode.storyboard_json = {
        "frames": [{
            "frame_id": "shot-needs-scope",
            "duration": 2,
            "image_prompt": "A",
            "video_prompt": "B",
        }]
    }
    db.flush()
    service = AITextArtifactService(db)
    manual = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
        source_type="human_edit",
        content_json={
            "episode_number": 1,
            "episode_goal": "Use scoped assets",
            "character_ids": [character.id],
            "scene_ids": [scene.id],
            "asset_usage": {
                "characters": [{"id": character.id, "name": character.name, "source": "existing", "usage": "Lead"}],
                "scenes": [{"id": scene.id, "name": scene.name, "source": "existing", "usage": "Room"}],
            },
        },
        content_text="Use scoped assets",
    )
    service.approve_artifact(manual.id)
    db.commit()
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 2,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    db.refresh(episode)
    frame = episode.storyboard_json["frames"][0]
    assert frame["scene_id"] == scene.id
    assert frame["character_ids"] == [character.id]
    plan = db.query(ProductionPlan).one()
    production_episode = db.query(ProductionEpisode).filter_by(plan_id=plan.id, episode_id=episode.id).one()
    production_scene = db.query(ProductionScene).filter_by(episode_plan_id=production_episode.id).one()
    production_shot = db.query(ProductionShot).filter_by(scene_plan_id=production_scene.id).one()
    assert production_scene.scene_id == scene.id
    assert production_shot.character_ids == [character.id]


def test_start_flow_preserves_asset_director_empty_frame_character_ids(db):
    series, episode = _series_episode(db)
    character = Character(name="Director Lead", role_type="protagonist", gender="female")
    scene = Scene(name="Director Room", scene_type="indoor")
    series.characters.append(character)
    series.scenes.append(scene)
    db.flush()
    episode.script_json = {
        "episode_asset_scope": {
            "source": "asset_director",
            "character_ids": [character.id],
            "scene_ids": [scene.id],
        }
    }
    episode.storyboard_json = {
        "frames": [
            {
                "frame_id": "shot-empty",
                "scene_id": scene.id,
                "character_ids": [],
                "duration": 1,
                "image_prompt": "An empty room.",
                "video_prompt": "Hold on the empty room.",
            },
            {
                "frame_id": "shot-lead",
                "scene_id": scene.id,
                "character_ids": [character.id],
                "duration": 1,
                "image_prompt": "The lead enters.",
                "video_prompt": "The lead enters.",
            },
        ]
    }
    db.commit()
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 2,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    db.refresh(episode)
    frames = {frame["frame_id"]: frame for frame in episode.storyboard_json["frames"]}
    assert frames["shot-empty"]["character_ids"] == []
    assert frames["shot-lead"]["character_ids"] == [character.id]
    shots = {shot.shot_id: shot for shot in db.query(ProductionShot).all()}
    assert shots["shot-empty"].character_ids == []
    assert shots["shot-lead"].character_ids == [character.id]



def test_start_flow_replaces_stale_storyboard_frame_asset_ids_with_episode_scope(db):
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

    series, episode = _series_episode(db)
    series.story_bible_json = {"style_lock": {"locked": True, "version": 1, "visual_style": {}}}
    character = Character(name="Current Lead", role_type="protagonist", gender="female")
    scene = Scene(name="Current Room", scene_type="indoor")
    series.characters.append(character)
    series.scenes.append(scene)
    episode.storyboard_json = {
        "frames": [{
            "frame_id": "shot-stale-frame-scope",
            "scene_id": "old-scene-id",
            "character_ids": ["old-character-id"],
            "duration": 2,
            "image_prompt": "A",
            "video_prompt": "B",
        }]
    }
    db.flush()
    service = AITextArtifactService(db)
    manual = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
        source_type="human_edit",
        content_json={
            "episode_number": 1,
            "episode_goal": "Replace stale frame IDs",
            "character_ids": [character.id],
            "scene_ids": [scene.id],
        },
        content_text="Replace stale frame IDs",
    )
    service.approve_artifact(manual.id)
    db.commit()
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 2,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    db.refresh(episode)
    frame = episode.storyboard_json["frames"][0]
    assert frame["scene_id"] == scene.id
    assert frame["character_ids"] == [character.id]
    production_scene = db.query(ProductionScene).one()
    production_shot = db.query(ProductionShot).one()
    assert production_scene.scene_id == scene.id
    assert production_shot.character_ids == [character.id]


def test_start_flow_retimes_existing_storyboard_to_target_duration(db):
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

    series, episode = _series_episode(db)
    character = Character(name="Timing Lead", role_type="protagonist", gender="female")
    scene = Scene(name="Timing Room", scene_type="indoor")
    series.characters.append(character)
    series.scenes.append(scene)
    episode.storyboard_json = {
        "frames": [
            {
                "frame_id": "shot-timing-1",
                "scene_id": scene.id,
                "character_ids": [character.id],
                "duration": 2,
                "image_prompt": "A",
                "video_prompt": "B",
            },
            {
                "frame_id": "shot-timing-2",
                "scene_id": scene.id,
                "character_ids": [character.id],
                "duration": 2,
                "image_prompt": "C",
                "video_prompt": "D",
            },
        ]
    }
    db.flush()
    service = AITextArtifactService(db)
    manual = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
        source_type="human_edit",
        content_json={
            "episode_number": 1,
            "episode_goal": "Retimed production",
            "character_ids": [character.id],
            "scene_ids": [scene.id],
        },
        content_text="Retimed production",
    )
    service.approve_artifact(manual.id)
    db.commit()
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    db.refresh(episode)
    assert episode.storyboard_json["total_duration"] == 10.0
    assert [frame["time_range"] for frame in episode.storyboard_json["frames"]] == ["0-5秒", "5-10秒"]
    segments = db.query(ProductionSegment).all()
    assert sum(float(segment.duration_seconds) for segment in segments) == 10.0


def test_start_flow_blocks_ambiguous_multi_scene_scope_without_frame_scene_ids(db):
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

    series = Series(
        title="Ambiguous Scope",
        logline="One sentence",
        genre="drama",
        target_duration=2,
        story_bible_json={"style_lock": {"locked": True, "version": 1, "visual_style": {}}},
    )
    character = Character(name="Lead", role_type="protagonist", gender="female")
    room = Scene(name="Room", scene_type="indoor")
    street = Scene(name="Street", scene_type="outdoor")
    series.characters.append(character)
    series.scenes.extend([room, street])
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={
            "frames": [{
                "frame_id": "shot-ambiguous-scene",
                "scene_number": 1,
                "character_ids": [character.id],
                "duration": 2,
                "image_prompt": "A",
                "video_prompt": "B",
            }]
        },
    )
    db.add(episode)
    db.flush()
    service = AITextArtifactService(db)
    manual = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
        source_type="human_edit",
        content_json={
            "episode_number": 1,
            "episode_goal": "Multiple scenes without mapping",
            "character_ids": [character.id],
            "scene_ids": [room.id, street.id],
        },
        content_text="Multiple scenes without mapping",
    )
    service.approve_artifact(manual.id)
    db.commit()
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 2,
        "autostart_images": False,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "EPISODE_ASSET_SCOPE_MISSING"


def test_start_flow_imports_existing_text_inputs_as_consumed_artifacts(db):
    series, episode = _series_episode(db)
    episode.script_json = {"scenes": [{"summary": "script scene"}]}
    db.commit()
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    consumed = resp.json()["run"]["consumed_text_artifacts"]
    assert [item["artifact_type"] for item in consumed] == [
        "series_bible",
        "series_story_plan",
        "season_arc",
        "continuity_ledger",
        "episode_outline",
        "episode_script",
        "storyboard",
        "dialogue",
        "image_prompt",
        "video_prompt",
    ]
    assert {item["status"] for item in consumed} == {"approved"}
    assert {item["source_type"] for item in consumed} == {"ai", "system_backfill", "system_import"}
    assert consumed[5]["metadata_json"]["source"] == "start_episode_production"


def test_start_flow_blocks_when_latest_text_artifact_revision_is_unapproved(db):
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

    series, episode = _series_episode(db)
    service = AITextArtifactService(db)
    service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="storyboard",
        source_type="human_edit",
        content_json={"frames": [{"frame_id": "needs-approval"}]},
        status="review_pending",
    )
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": False,
    })

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["error_code"] == "TEXT_ARTIFACT_REVIEW_REQUIRED"
    assert detail["repair_route"] == f"/series/{series.id}/ai-text-artifacts"
    assert detail["affected_ids"]


def test_start_flow_binds_latest_approved_text_artifacts_to_run(db):
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

    series, episode = _series_episode(db)
    service = AITextArtifactService(db)
    old_storyboard = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="storyboard",
        source_type="ai",
        content_json={"frames": [{"frame_id": "old"}]},
    )
    service.approve_artifact(old_storyboard.id)
    latest_storyboard = service.edit_artifact(
        old_storyboard.id,
        content_json={"frames": [{"frame_id": "latest"}]},
        content_text="latest storyboard",
    )
    service.approve_artifact(latest_storyboard.id)
    series_bible = service.create_artifact(
        series_id=series.id,
        target_type="series",
        target_id=series.id,
        artifact_type="series_bible",
        source_type="ai",
        content_json={"logline": "approved bible"},
    )
    service.approve_artifact(series_bible.id)
    asset_director = service.create_artifact(
        series_id=series.id,
        target_type="series",
        target_id=series.id,
        artifact_type="asset_director_plan",
        source_type="ai",
        content_json={"readiness": {"status": "ready"}},
    )
    service.approve_artifact(asset_director.id)
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    run_id = resp.json()["run"]["id"]
    consumed = resp.json()["run"]["consumed_text_artifacts"]
    assert [(item["artifact_type"], item["version"]) for item in consumed] == [
        ("series_bible", 1),
        ("series_story_plan", 1),
        ("season_arc", 1),
        ("continuity_ledger", 1),
        ("asset_director_plan", 1),
        ("episode_outline", 1),
        ("episode_script", 1),
        ("storyboard", 2),
        ("dialogue", 1),
        ("image_prompt", 1),
        ("video_prompt", 1),
    ]
    consumed_by_type = {item["artifact_type"]: item for item in consumed}
    assert consumed_by_type["series_bible"]["artifact_id"] == series_bible.id
    assert consumed_by_type["asset_director_plan"]["artifact_id"] == asset_director.id
    assert consumed_by_type["storyboard"]["artifact_id"] == latest_storyboard.id
    assert db.query(AITextArtifactConsumer).filter_by(
        consumer_type="video_production_run",
        consumer_id=run_id,
        artifact_id=latest_storyboard.id,
    ).count() == 1
    assert db.query(AITextArtifactConsumer).filter_by(
        consumer_type="video_production_run",
        consumer_id=run_id,
        artifact_id=old_storyboard.id,
    ).count() == 0


def test_start_flow_uses_approved_storyboard_artifact_as_production_input(db):
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

    series, episode = _series_episode(db)
    episode.storyboard_json = {
        "frames": [{
            "frame_id": "stale-shot",
            "scene_id": "scene-1",
            "duration": 6,
            "image_prompt": "stale image prompt",
            "video_prompt": "stale video prompt",
        }]
    }
    db.commit()
    service = AITextArtifactService(db)
    artifact = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="storyboard",
        source_type="human_edit",
        content_json={
            "frames": [{
                "frame_id": "approved-shot",
                "scene_id": "scene-1",
                "character_ids": ["char-1"],
                "duration": 6,
                "image_prompt": "approved image prompt",
                "video_prompt": "approved video prompt",
                "narration": "approved narration",
                "reference_urls": ["/static/characters/laoli-front.png"],
            }]
        },
        content_text="approved storyboard text",
    )
    service.approve_artifact(artifact.id)
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 6,
        "autostart_images": False,
    })

    assert resp.status_code == 200
    body = resp.json()
    run = db.query(VideoProductionRun).filter_by(id=body["run"]["id"]).one()
    segment = db.query(ProductionSegment).one()
    db.refresh(episode)

    assert run.storyboard_json["frames"][0]["frame_id"] == "approved-shot"
    assert episode.storyboard_json["frames"][0]["frame_id"] == "approved-shot"
    assert segment.segment_id == "approved-shot-seg-01"
    assert segment.image_prompt == "approved image prompt"
    assert segment.video_prompt == "approved video prompt"
    consumed_by_type = {item["artifact_type"]: item for item in body["run"]["consumed_text_artifacts"]}
    assert consumed_by_type["storyboard"]["artifact_id"] == artifact.id


def test_backfill_run_text_artifacts_endpoint_returns_consumed_versions(db):
    series, episode = _series_episode(db)
    episode.script_json = {"scenes": [{"summary": "legacy script"}]}
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="completed",
        current_stage="completed",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.commit()
    client = TestClient(app)

    resp = client.post(f"/api/video-production/runs/{run.id}/backfill-text-artifacts")

    assert resp.status_code == 200
    consumed = resp.json()["run"]["consumed_text_artifacts"]
    assert [item["artifact_type"] for item in consumed] == [
        "series_bible",
        "continuity_ledger",
        "episode_outline",
        "episode_script",
        "storyboard",
        "dialogue",
        "image_prompt",
        "video_prompt",
    ]
    assert resp.json()["consumed_text_artifacts"] == consumed


def test_start_flow_preserves_real_short_run_type_from_request(db):
    series, episode = _series_episode(db)
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 60,
        "budget_limit": 1,
        "autostart_images": False,
        "run_type": REAL_SHORT_E2E,
    })

    assert resp.status_code == 200
    run = db.query(VideoProductionRun).filter_by(id=resp.json()["run"]["id"]).one()
    plan = db.query(ProductionPlan).filter_by(id=run.production_plan_id).one()
    assert run.run_type == REAL_SHORT_E2E
    assert plan.budget_limit == 1


def test_real_short_start_flow_autostart_images_enqueues_without_synchronous_agency_review(db, monkeypatch):
    series, episode = _series_episode(db)
    client = TestClient(app)

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("start flow must not synchronously run agency review")

    monkeypatch.setattr("app.domains.video_production.video_production_service._guard_provider_stage", fail_if_called)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "budget_limit": 1,
        "run_type": REAL_SHORT_E2E,
    })

    assert resp.status_code == 200
    run = db.query(VideoProductionRun).filter_by(id=resp.json()["run"]["id"]).one()
    assert run.status == "image_batch_running"
    assert run.model_trace_json["autopilot"] == {"enabled": True, "source": "episode_start"}
    assert db.query(ProductionJob).filter_by(plan_id=run.production_plan_id, stage="image_generation").count() == 2


def test_start_flow_creates_isolated_plan_and_jobs_for_each_run(db):
    series, episode = _series_episode(db)
    client = TestClient(app)

    first = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "budget_limit": 1,
        "run_type": REAL_SHORT_E2E,
    })
    second = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 10,
        "budget_limit": 1,
        "run_type": REAL_SHORT_E2E,
    })

    assert first.status_code == 200
    assert second.status_code == 200
    first_plan_id = first.json()["run"]["production_plan_id"]
    second_plan_id = second.json()["run"]["production_plan_id"]
    assert first_plan_id != second_plan_id
    assert db.query(ProductionJob).filter_by(plan_id=first_plan_id, stage="image_generation").count() == 2
    assert db.query(ProductionJob).filter_by(plan_id=second_plan_id, stage="image_generation").count() == 2


def test_start_flow_rejects_mock_series_scale_before_linked_plan_mutation(db):
    series, episode = _series_episode(db)
    client = TestClient(app)

    before = {
        "runs": db.query(VideoProductionRun).count(),
        "plans": db.query(ProductionPlan).count(),
    }
    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "target_duration_seconds": 240 * 60,
        "autostart_images": False,
        "run_type": MOCK_SERIES_SCALE,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "INVALID_RUN_TYPE"
    assert {
        "runs": db.query(VideoProductionRun).count(),
        "plans": db.query(ProductionPlan).count(),
    } == before


def test_start_flow_returns_repairable_error_when_style_is_unlocked(db):
    series, episode = _series_episode(db, locked=False)
    client = TestClient(app)

    resp = client.post("/api/video-production/runs/start", json={
        "series_id": series.id,
        "episode_id": episode.id,
        "autostart_images": False,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "STYLE_LOCK_MISSING"
